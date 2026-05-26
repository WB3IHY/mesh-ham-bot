# modules/games

Games (blackjack, dopewars, golfsim, lemonade, tictactoe, mastermind, videopoker,
battleship, hangman, hamtest, quiz, survey, wordOfTheDay) were removed when this
project was forked from meshing-around.

Only `joke.py` remains.

## joke

Tells a random dad joke via the [icanhazdadjoke.com](https://icanhazdadjoke.com/) API.

| Command | Description        |
|---------|--------------------|
| `joke`  | Returns a dad joke |

Enable in `[general]` section of `config.ini`:

```ini
[general]
DadJokes = True
DadJokesEmoji = False
```
