#
all: a339dev

a339dev:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p `cat packdev.txt`

a321dev:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A321 -p `cat packdev.txt`

a321:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A321 -p `cat packages.txt`

a339:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p `cat packages.txt`

clean:
	rm -f cockpitdecks.log events.json commands.json datarefs.json webapi.log variable-datatase-dump.yaml webapi-datarefs.json webapi-commands.json

black:
	sh blackall.sh

git:
	sh gitall.sh
