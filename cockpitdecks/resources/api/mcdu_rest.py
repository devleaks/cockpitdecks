import logging

from api import Cache, API

from mcdu import MCDU

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    api = API(host="192.168.1.140", port=8080)
    # api.set_api("vx")
    api.set_api()
    all_datarefs = Cache(api)
    all_datarefs.load("/datarefs")
    all_datarefs.save("test-datarefs.json")

    mcdu = MCDU()
    data = mcdu.get_variables()
    mcdu.datarefs = {d: all_datarefs.get_by_name(d) for d in data}
    print("collecting one by one, it takes a few seconds..")
    # mcdu.save("mcdu.out")
    mcdu.build_screen()
    print("..collected")
    mcdu.show_screen()
