# Internal datarefs (stats, performance)
from enum import Enum


class INTERNAL_DATAREF(Enum):
    #
    # C O C K P I T D E C K S
    #

    #
    # C O C K P I T
    #
    # Number of cockpitdecks reloads
    COCKPITDECK_RELOADS = "reload_pages"

    #
    # D E C K
    #
    # Number of page reloads
    DECK_RELOADS = "reload_page"  # /<deck-name>

    # Number of page reloads
    PAGE_CHANGES = "change_page"  # /<deck-name>/<page-name>

    RENDER_BG_TEXTURE = "bg-texture"
    RENDER_BG_COLOR = "bg-color"
    RENDER_CREATE_ICON = "create_icon"

    #
    # P A G E
    #
    DATAREF_REGISTERED = "registered_dataref"
    PAGE_RENDER = "page_render"
    PAGE_CLEAN = "page_clean"

    #
    # B U T T O N
    #
    BUTTON_ACTIVATIONS = "activation"
    BUTTON_RENDERS = "render"
    BUTTON_REPRESENTATIONS = "representation"
    BUTTON_CLEAN = "clean"

    # ACTIVATION
    ACTIVATION_COMPLETED = "activation_completed"
    ACTIVATION_DURATION = "activation_duration"
    ACTIVATION_COUNT = "activation_count"
    ACTIVATION_RELEASE = "release_count"
    ENCODER_TURNS = "turns"
    ENCODER_CLOCKWISE = "cw"
    ENCODER_COUNTER_CLOCKWISE = "ccw"
    ACTIVATION_LONGPUSH = "long-push"
    ACTIVATION_SHORTPUSH = "short-push"
    ACTIVATION_ON = "on"
    ACTIVATION_OFF = "off"

    #
    # U D P
    #
    INTDREF_CONNECTION_STATUS = "_connection_status"
    # Number of UDP packet received
    UDP_BEACON_RCV = "udp_beacon_received"
    UDP_BEACON_TIMEOUT = "udp_beacon_timeout"
    STARTS = "starts"
    STOPS = "stops"

    UDP_READS = "udp_rcv"
    LAST_READ = "last_read_time"
    VALUES = "values_read"
    UPDATE_ENQUEUED = "value_change_enqueued"

    # Average number of reads per seconds (last 100 reads)
    UDP_READS_PERSEC = "cockpitdecks/udp/persec"

    # Time sice last read
    UDP_CYCLE = "cockpitdecks/udp/cycle"

    # Average number of dataref values recevied per seconds (last two minutes)
    UDP_DATAREFS_PERSEC = "cockpitdecks/udp/datarefs_persec"

    # Total number of dataref values recevied
    UDP_DATAREF_COUNT = "cockpitdecks/udp/dataref-count"

    #
    # E V E N T
    #
    ENQUEUE_CYCLE = "cockpitdecks/udp/enqueue/cycle"

    ENQUEUE_COUNT = "cockpitdecks/udp/enqueue/count"

    ENQUEUE_PERSEC = "cockpitdecks/udp/enqueue/persec"

    #
    # X - P L A N E
    #
    # Zulu diff
    # Time difference between zulu in sim and zulu on cockpitdecks host computer (in seconds and microseconds)
    ZULU_DIFFERENCE = "xplane/timedelay"
    ZULU_CNT = "xplane/timedelay/cnt"
    ZULU_AVG = "xplane/timedelay/avg"
    ZULU_MIN = "xplane/timedelay/min"
    ZULU_MAX = "xplane/timedelay/max"
