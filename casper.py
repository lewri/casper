from pprint import pprint
import asyncio
import logging
import os

from discord.ext import commands
import youtube_dl
import discord

import config

if not discord.opus.is_loaded():
    discord.opus.load_opus('opus')


logging.basicConfig(level=logging.INFO)


class VoiceEntry:
    def __init__(self, message, player, song_info):
        self.requester = message.author
        self.channel = message.channel
        self.player = player
        self.song_info = song_info

    def __str__(self):
        duration = self.song_info['duration']
        if not duration:
            duration = 0
        return '{0} uploaded by {1} - requested by {2} [length: {3[0]}m {3[1]}s]'.format(
            self.song_info['title'],
            self.song_info['uploader'],
            self.requester.display_name,
            divmod(duration, 60),
        )


class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.skip_votes = set()
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
            self.current.player.start()
            await self.play_next_song.wait()


class Music:
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def create_voice_client(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    def __unload(self):
        for state in self.voice_states.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """
        Summon casper into your current voice channel.
        """

        if config.DEV_MODE and ctx.message.author.id != config.DEV_ID:
            await self.bot.say(
                'I am currently running in dev mode, and will not respond to non-admin commands.')
            return False

        summoned_channel = ctx.message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True

    @commands.command(pass_context=True, no_pm=True)
    async def yt(self, ctx, *, song: str):
        """
        Request a song from youtube.
        """
        if config.DEV_MODE and ctx.message.author.id != config.DEV_ID:
            await self.bot.say(
                'I am currently running in dev mode, and will not respond to non-admin commands.')
            return False

        state = self.get_voice_state(ctx.message.server)
        ytdl_opts = {
            'source_address': '0.0.0.0',
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': "mp3",
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': 'cache/audio/%(id)s',
            'default_search': 'auto',
        }

        if state.voice is None:
            success = await ctx.invoke(self.summon)
            if not success:
                return

        await self.bot.say('Searching for "{}"...'.format(song))

        try:
            with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
                logging.info('Getting song info...')
                info = ytdl.extract_info(song, download=False)['entries'][0]
                song_file = 'cache/audio/{}'.format(info['id'])
                logging.info('Song file: {}'.format(song_file))
                if not os.path.isfile(song_file):
                    logging.info('New song, downloading to {}'.format(song_file))
                    ytdl.download([song])
                    logging.info('Finished downloading song to {}'.format(song_file))
            logging.info('Creating player for {}'.format(song_file))
            player = state.voice.create_ffmpeg_player(
                song_file,
                after=state.toggle_next,
                options='-b:a 64k -bufsize 64k')
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
        else:
            logging.info('Creating voice entry for {}'.format(song_file))
            entry = VoiceEntry(ctx.message, player, info)
            logging.info(entry)

            if state.current is not None:
                await self.bot.say('Enqueued ' + str(entry))
            await state.songs.put(entry)

    @commands.command(pass_context=True, no_pm=True)
    async def stop(self, ctx):
        """
        Stop the music session entirely.
        """
        if config.DEV_MODE and ctx.message.author.id != config.DEV_ID:
            await self.bot.say(
                'I am currently running in dev mode, and will not respond to non-admin commands.')
            return False

        server = ctx.message.server
        state = self.get_voice_state(server)

        if state.is_playing():
            player = state.player
            player.stop()
            await self.bot.say('Stopped.')
        else:
            await self.bot.say('Can\'t stop won\'t stop! (I\'m not currently playing anything...)')

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """
        Skip the current song.
        """
        if config.DEV_MODE and ctx.message.author.id != config.DEV_ID:
            await self.bot.say(
                'I am currently running in dev mode, and will not respond to non-admin commands.')
            return False

        state = self.get_voice_state(ctx.message.server)
        if not state.is_playing():
            await self.bot.say('Can\'t skip what ain\'t there!')
            return

        voter = ctx.message.author
        if voter == state.current.requester:
            await self.bot.say('Skipping song...')
            state.skip()
        elif voter.id not in state.skip_votes:
            state.skip_votes.add(voter.id)
            total_votes = len(state.skip_votes)
            if total_votes >= 3:
                await self.bot.say('Skip vote passed, skipping song...')
                state.skip()
            else:
                await self.bot.say('Skip vote added, currently at [{}/3]'.format(total_votes))
        else:
            await self.bot.say('You have already voted to skip this song.')

    @commands.command(pass_context=True, no_pm=True)
    async def playing(self, ctx):
        """
        Show information for the song currently playing.
        """
        if config.DEV_MODE and ctx.message.author.id != config.DEV_ID:
            await self.bot.say(
                'I am currently running in dev mode, and will not respond to non-admin commands.')
            return False

        state = self.get_voice_state(ctx.message.server)
        if state.current is None:
            await self.bot.say('I\'m not playing anything...')
        else:
            skip_count = len(state.skip_votes)
            await self.bot.say('Now playing {} [skips: {}/3]'.format(state.current, skip_count))


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or('!'),
    description='Casper the friendly music bot')
bot.add_cog(Music(bot))


@bot.event
async def on_ready():
    print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))

bot.run(config.TOKEN)
