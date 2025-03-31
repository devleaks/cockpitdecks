#
ALL_PACKAGES = /Users/pierre/Developer/fs/cockpitdecks_xp /Users/pierre/Developer/fs/cockpitdecks_ext /Users/pierre/Developer/fs/cockpitdecks_tl /Users/pierre/Developer/fs/cockpitdecks_wm /Users/pierre/Developer/fs/cockpitdecks_sd /Users/pierre/Developer/fs/cockpitdecks_ld /Users/pierre/Developer/fs/cockpitdecks_bx
DEV_PACKAGES = /Users/pierre/Developer/fs/cockpitdecks_xp /Users/pierre/Developer/fs/cockpitdecks_ext /Users/pierre/Developer/fs/cockpitdecks_tl /Users/pierre/Developer/fs/cockpitdecks_wm /Users/pierre/Developer/fs/cockpitdecks_sd
TEMPDIR := $(shell mktemp -p . -d --dry-run)

all: a339dev

a339dev:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p $(DEV_PACKAGES)

a321dev:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A321 -p $(DEV_PACKAGES)

test:
	clear
	@cockpitdecks-cli aircrafts/tests --fixed -p $(DEV_PACKAGES)

a321:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A321 -p $(ALL_PACKAGES)

a339:
	clear
	@cockpitdecks-cli aircrafts/ToLiss\ A339 -p $(ALL_PACKAGES)

keep:
	@mkdir $(TEMPDIR)
	@mv events.json datarefs.json webapi-commands.json webapi-datarefs.json webapi.log variable-database-dump.yaml $(TEMPDIR)
	@echo saved in $(TEMPDIR)

clean:
	@rm -f events.json variable-database-dump.yaml 
	@rm -f commands.json datarefs.json webapi-datarefs.json webapi-commands.json webapi.log
	@rm -f cockpitdecks.log
	@echo cleaned

black:
	@sh blackall.sh

git:
	@sh gitall.sh
