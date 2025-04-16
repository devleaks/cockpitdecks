#
ALL_PACKAGES = /Users/pierre/Developer/fs/cockpitdecks_xp /Users/pierre/Developer/fs/cockpitdecks_ext /Users/pierre/Developer/fs/cockpitdecks_tl /Users/pierre/Developer/fs/cockpitdecks_wm /Users/pierre/Developer/fs/cockpitdecks_sd /Users/pierre/Developer/fs/cockpitdecks_ld /Users/pierre/Developer/fs/cockpitdecks_bx
DEV_PACKAGES = /Users/pierre/Developer/fs/cockpitdecks_xp /Users/pierre/Developer/fs/cockpitdecks_ext /Users/pierre/Developer/fs/cockpitdecks_tl /Users/pierre/Developer/fs/cockpitdecks_wm /Users/pierre/Developer/fs/cockpitdecks_sd
TEMPDIR := $(shell mktemp -p . -d --dry-run)

define git_one
    echo "\n\n--- $1"
    (cd  ../$1; git status)
endef


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

demo:
	clear
	@cockpitdecks-cli --demo --fixed -p $(DEV_PACKAGES)

keep:
	@mkdir $(TEMPDIR)
	@mv events.json datarefs.json webapi-commands.json webapi-datarefs.json webapi.log variable-database-dump.yaml $(TEMPDIR)
	@echo saved in $(TEMPDIR)

autoreload:
	@nodemon -w aircrafts/*/deckconfig/resources/decks/types -e yaml --exec curl "http://127.0.0.1:7777/reload-decks"

clean:
	@rm -f events.json variable-database-dump.yaml 
	@rm -f commands.json datarefs.json webapi-datarefs.json webapi-commands.json webapi.log
	@rm -f cockpitdecks.log
	@echo cleaned

black:
	# core
	@black ../cockpitdecks/cockpitdecks
	# sims
	@black ../cockpitdecks_xp/cockpitdecks_xp
	@black ../cockpitdecks_fs/cockpitdecks_fs
	# decks
	@black ../cockpitdecks_ld/cockpitdecks_ld
	@black ../cockpitdecks_sd/cockpitdecks_sd
	@black ../cockpitdecks_bx/cockpitdecks_bx
	# ext
	@black ../cockpitdecks_ext/cockpitdecks_ext
	@black ../cockpitdecks_wm/cockpitdecks_wm
	@black ../cockpitdecks_tl/cockpitdecks_tl
	# templates
	@black ../cockpitdecks_dev/cockpitdecks_dev
	@black ../cockpitdecks_wd/cockpitdecks_wd

git:
	@$(call git_one,"cockpitdecks")
	@$(call git_one,"cockpitdecks_xp")
	@$(call git_one,"cockpitdecks_ld")
	@$(call git_one,"cockpitdecks_sd")
	@$(call git_one,"cockpitdecks_bx")
	@$(call git_one,"cockpitdecks_ext")
	@$(call git_one,"cockpitdecks_tl")
	@$(call git_one,"cockpitdecks_wm")
	@$(call git_one,"cockpitdecks_dev")
	@$(call git_one,"cockpitdecks_wd")
