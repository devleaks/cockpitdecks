#
all: default_development_run

default_development_run:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p `cat packdev.txt`

clean:
	rm -f cockpitdecks.log events.json commands.json datarefs.json webapi.log variable-datatase-dump.yaml webapi-datarefs.json webapi-commands.json

black:
	sh blackall.sh

git:
	sh gitall.sh
