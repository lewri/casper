# NB: This isn't maintained and was moved from Gitlab/backwardspy/casper. Feel free to fork it and make it work. #

# Casper

## The friendly discord music bot

### Requirements
- python 3.5+
- pip
- opus
- ffmpeg

Optional:
- virtualenv

### Usage

```
Music:
  playing Show information for the song currently playing.
  skip    Skip the current song.
  stop    Stop the music session entirely.
  summon  Summon casper into your current voice channel.
  yt      Request a song from youtube.
No Category:
  help    Shows this message.

Type !help command for more info on a command.
You can also type !help category for more info on a category.
```

### Setup

1. Clone & enter repository with `git clone git@gitlab.com:BackwardSpy/casper.git && cd casper`.
2. [optional] Create a virtual environment with `virtualenv ~/.virtualenvs/casper --python=python3`.
3. Install requirements with `pip install -r requirements`.
4. Create a config with `cp config.example.py config.py` and add your app key (obtained [here](https://discordapp.com/developers/applications/me)).
5. Invite the bot to your server (instructions for this can be found towards the bottom of [this page](https://discordapp.com/developers/docs/topics/oauth2)).
6. Run the bot with `python casper.py`.
7. Try the `!help` command to get started.
