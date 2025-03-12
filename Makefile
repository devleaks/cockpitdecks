#
clean:
	rm -f cockpitdecks.log events.json commands.json datarefs.json webapi.log variable-datatase-dump.yaml

black:
	sh blackall.sh

git:
	sh gitall.sh
