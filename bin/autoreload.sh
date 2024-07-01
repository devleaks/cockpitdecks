:
# install nodejs nodemon
nodemon -w aircrafts/*/deckconfig/resources/decks/types -e yaml --exec curl "http://127.0.0.1:7777/reload-decks"