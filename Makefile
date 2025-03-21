#
all: a339dev

a339dev:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p `cat packdev.txt`

a321dev:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A321 -p `cat packdev.txt`

test:
	clear
	@cockpitdecks-cli aircrafts/tests --fixed -p `cat packdev.txt`

a321:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A321 -p `cat packages.txt`

a339:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p `cat packages.txt`

clean:
	rm -f cockpitdecks.log
	rm -f events.json variable-database-dump.yaml 
	rm -f commands.json datarefs.json webapi-datarefs.json webapi-commands.json webapi.log

black:
	sh blackall.sh

git:
	sh gitall.sh
