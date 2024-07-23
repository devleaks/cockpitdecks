from enum import Enum


class INTERNAL_DATAREF(Enum):
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

