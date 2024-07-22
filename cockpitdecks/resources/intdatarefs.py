# Internal datarefs (stats, performance)

# Number of cockpitdecks reloads
COCKPITDECK_RELOADS = "cockpitdecks/cockpit/reloads"

# Number of page reloads
DECK_RELOADS = "cockpitdecks/cockpit/deck"  # /<deck-name>

# Number of page reloads
PAGE_RELOADS = "cockpitdecks/cockpit/page"  # /<deck-name>/<page-name>


# Number of UDP packet received
UDP_COUNT = "cockpitdecks/udp/count"

# Average number of reads per seconds (last 100 reads)
UDP_READS_PERSEC = "cockpitdecks/udp/persec"

# Time sice last read
UDP_CYCLE = "cockpitdecks/udp/cycle"

# Average number of dataref values recevied per seconds (last two minutes)
UDP_DATAREFS_PERSEC = "cockpitdecks/udp/datarefs_persec"

# Total number of dataref values recevied
UDP_DATAREF_COUNT = "cockpitdecks/udp/dataref-count"

ENQUEUE_CYCLE = "cockpitdecks/udp/enqueue/cycle"

ENQUEUE_COUNT = "cockpitdecks/udp/enqueue/count"

ENQUEUE_PERSEC = "cockpitdecks/udp/enqueue/persec"


# class DatarefStat:

#     def __init__(self, sim) -> None:
#         self.sim = sim
#         self._udp_count = sim.get_internal_dataref("/upd/count")

#     @dataref("/upd/count").getter
#     def udp_count(self):
#         return self._udp_count

#     @dataref("/upd/count").setter
#     def udp_count(self, value):
#         self._udp_count = value

#     @dataref("/upd/count").incer
#     def udp_count(self, value: float = 1):
#         self._udp_count = self._udp_count + value
