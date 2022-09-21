import logging

logger = logging.getLogger("XTouchMini")


from .deck import Deck

class XTouchMini(Deck):

    def __init__(self, name: str, config: dict, cockpit: "Cockpit", device = None):

        Deck.__init__(self, name=name, config=config, cockpit=cockpit, device=device)

        self.init()


    def init(self):
        self.device.set_callback(self.key_change_callback)
        self.start()


    def start(self):
        self.device.start()
        logger.debug(f"start: {self.name} started")


    def stop(self):
        self.device.stop()
        logger.debug(f"stop: {self.name} stopped")
