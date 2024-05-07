import socket
import threading
import logging
import time
import json

from typing import Dict, List
from datetime import datetime

from cockpitdecks.buttons.representation.animation import DrawAnimation
from cockpitdecks import ICON_SIZE

# ##############################
# Toliss Airbus FMA display
FMA_DATAREFS = {
    "1w": "AirbusFBW/FMA1w[:36]",
    "1g": "AirbusFBW/FMA1g[:36]",
    "1b": "AirbusFBW/FMA1b[:36]",
    "2w": "AirbusFBW/FMA2w[:36]",
    "2b": "AirbusFBW/FMA2b[:36]",
    "2m": "AirbusFBW/FMA2m[:36]",
    "3w": "AirbusFBW/FMA3w[:36]",
    "3b": "AirbusFBW/FMA3b[:36]",
    "3a": "AirbusFBW/FMA3a[:36]",
}
FMA_BOXES = [
    "AirbusFBW/FMAAPFDboxing",
    "AirbusFBW/FMAAPLeftArmedBox",
    "AirbusFBW/FMAAPLeftModeBox",
    "AirbusFBW/FMAAPRightArmedBox",
    "AirbusFBW/FMAAPRightModeBox",
    "AirbusFBW/FMAATHRModeBox",
    "AirbusFBW/FMAATHRboxing",
    "AirbusFBW/FMATHRWarning",
]
# Reproduction on Streamdeck touchscreen colors is difficult.
FMA_COLORS = {
    "b": "#0080FF",
    "w": "white",
    "g": "#00FF00",
    "m": "#FF00FF",
    "a": "#A04000",
}

FMA_LABELS = {
    "ATHR": "Auto Thrust",
    "VNAV": "Vertical Navigation",
    "LNAV": "Horizontal Navigation",
    "APPR": "Approach",
    "AP": "Auto Pilot",
}
FMA_LABELS_ALT = {
    "ATHR": "Autothrust Mode",
    "VNAV": "Vertical Mode",
    "LNAV": "Horizontal Mode",
    "APPR": "Approach",
    "AP": "Autopilot Mode",
}
FMA_LABEL_MODE = 3  # 0 (None), 1 (keys), or 2 (values), or 3 alternates

FMA_COUNT = len(FMA_LABELS.keys())
FMA_COLUMNS = [[0, 7], [7, 15], [15, 21], [21, 28], [28, 37]]
FMA_LINE_LENGTH = FMA_COLUMNS[-1][-1]
FMA_LINES = 3

ANY = "0.0.0.0"
FMA_MCAST_PORT = 49505
FMA_MCAST_GRP = "239.255.1.1"
FMA_UPDATE_FREQ = 1.0
FMA_SOCKET_TIMEOUT = FMA_UPDATE_FREQ + 5.0  # should be larger or equal to PI_string_datarefs_udp.FREQUENCY (= 5.0 default)

logger = logging.getLogger(__file__)
# logger.setLevel(logging.DEBUG)
# logger.setLevel(15)


class FMAIcon(DrawAnimation):
    """ """

    REPRESENTATION_NAME = "fma"

    def __init__(self, config: dict, button: "Button"):
        DrawAnimation.__init__(self, config=config, button=button)

        self._udp_inited = False
        self.fmaconfig = config.get("fma", {})  # should not be none, empty at most...
        self.all_in_one = False
        self.fma_label_mode = self.fmaconfig.get("label-mode", FMA_LABEL_MODE)
        self.icon_color = "black"
        self.text = {k: " " * FMA_LINE_LENGTH for k in FMA_DATAREFS}  # use FMA_LINES for testing
        self.previous_text: Dict[str, str] = {}
        self.boxed: List[str] = []
        self._cached = None  # cached icon

        # get mandatory index
        self.all_in_one = False
        fma = self.fmaconfig.get("index")
        if fma is None:
            logger.info(f"button {button.name}: no FMA index, assuming all-in-one")
            self.all_in_one = True
            fma = 1
        fma = int(fma)
        if fma < 1:
            logger.info(f"button {button.name}: FMA index must be in 1..{FMA_COUNT} range")
            fma = 1
        if fma > FMA_COUNT:
            logger.info(f"button {button.name}: FMA index must be in 1..{FMA_COUNT} range")
            fma = FMA_COUNT
        self.fma_idx = fma - 1

        self.collect_fma: threading.Event | None = None
        self.update_fma: threading.Event | None = None
        self.fma_collector_thread: threading.Thread | None = None
        self.fma_updater_thread: threading.Thread | None = None

        self.fma_text: Dict[str, Dict] = {}
        self.fma_text_lock = threading.RLock()

        self.socket = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # Allow multiple sockets to use the same PORT number
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # SO_REUSEPORT
        # Bind to the port that we know will receive multicast data
        # self.socket.bind((ANY, FMA_MCAST_PORT))
        # status = self.socket.setsockopt(
        #     socket.IPPROTO_IP,
        #     socket.IP_ADD_MEMBERSHIP,
        #     socket.inet_aton(FMA_MCAST_GRP) + socket.inet_aton(ANY),
        # )
        self.collector_avgtime = 0
        self.init_udp()

    def init_udp(self):
        if self._udp_inited:
            return
        # Bind to the port that we know will receive multicast data
        try:
            self.socket.bind((ANY, FMA_MCAST_PORT))
            status = self.socket.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                socket.inet_aton(FMA_MCAST_GRP) + socket.inet_aton(ANY),
            )
            logger.debug("..socket bound..")
            self._udp_inited = True
        except:
            logger.info("socket bind return error", exc_info=True)

    def should_run(self) -> bool:
        return True

    def is_master_fma(self) -> bool:
        return self.all_in_one or self.fma_idx == 1

    def get_master_fma(self):
        """Among all FMA icon buttons on the same page, tries to find the master one,
        i;e. the one that holds the datarefs.
        """
        if self.is_master_fma():
            return self
        candidates = list(
            filter(
                lambda m: isinstance(m._representation, FMAIcon) and m._representation.is_master_fma(),
                self.button.page.buttons.values(),
            )
        )
        if len(candidates) == 1:
            logger.debug(f"button {self.button.name}: master FMA is {candidates[0].name}, fma={candidates[0]._representation.fma_idx}")
            return candidates[0]._representation
        if len(candidates) == 0:
            logger.warning(f"button {self.button.name}: no master FMA found")
        else:
            logger.warning(f"button {self.button.name}: too many master FMA")
        return None

    def collector(self):
        logger.info("starting FMA collector..")
        total_to = 0
        total_reads = 0
        last_read_ts = datetime.now()
        total_read_time = 0.0
        src_last_ts = 0
        src_cnt = 0
        src_tot = 0

        while self.collect_fma is not None and not self.collect_fma.is_set():
            try:
                self.socket.settimeout(max(FMA_SOCKET_TIMEOUT, FMA_UPDATE_FREQ))
                data, addr = self.socket.recvfrom(1472)
                total_to = 0
                total_reads = total_reads + 1
                now = datetime.now()
                delta = now - last_read_ts
                total_read_time = total_read_time + delta.microseconds / 1000000
                last_read_ts = now
                logger.debug(f"FMA collector: got data")  # ({data})
            except:
                total_to = total_to + 1
                logger.debug(
                    f"FMA collector: socket timeout received ({total_to})",
                    exc_info=(logger.level == logging.DEBUG),
                )
            else:
                with self.fma_text_lock:
                    data = json.loads(data.decode("utf-8"))
                    ts = 0
                    if "ts" in data:
                        ts = data["ts"]
                        del data["ts"]
                        if src_last_ts > 0:
                            src_tot = src_tot + (ts - src_last_ts)
                            src_cnt = src_cnt + 1
                            self.collector_avgtime = src_tot / src_cnt
                            if src_cnt % 100 == 0:
                                logger.info(f"FMA collector: average time between reads {round(self.collector_avgtime, 4)}")
                        src_last_ts = ts
                    self.fma_text = {k: data.get("AirbusFBW/FMA" + k, "") for k in FMA_DATAREFS}  # this is to adjust to older algorithm...
                # logger.debug(f"from {addr} at {ts}: data: {self.text}")
        self.collect_fma = None
        # Bind to the port that we know will receive multicast data
        # self.socket.shutdown()
        # self.socket.close()
        # logger.info("..socket closed..")
        logger.debug("..FMA collector terminated")

    def updator(self):
        logger.debug("starting FMA updater..")
        # total_to = 0
        # total_reads = 0
        # total_values = 0
        # last_read_ts = datetime.now()
        # total_read_time = 0.0
        while self.update_fma is not None and not self.update_fma.is_set():
            with self.fma_text_lock:
                self.text = self.fma_text.copy()
            self.button.render()
            time.sleep(max(FMA_UPDATE_FREQ, self.collector_avgtime))  # autotune update frequency
        self.update_fma = None
        logger.debug("..FMA updater terminated")

    def is_updated(self) -> bool:
        oldboxed = self.boxed
        self.check_boxed()
        if self.boxed != oldboxed:
            logger.debug(f"boxed changed {self.boxed}/{oldboxed}")
            return True
        return self.text != self.previous_text

    def anim_start(self) -> None:
        if self.running:
            logger.debug("anim already running")
        if self.collect_fma is None:
            self.collect_fma = threading.Event()
            self.fma_collector_thread = threading.Thread(target=self.collector)
            self.fma_collector_thread.name = "FMA::collector"
            self.fma_collector_thread.start()
            logger.info("FMA collector started")
        else:
            logger.info("FMA collector already running.")
        if self.update_fma is None:
            self.update_fma = threading.Event()
            self.fma_updater_thread = threading.Thread(target=self.updator)
            self.fma_updater_thread.name = "FMA::updater"
            self.fma_updater_thread.start()
            logger.info("FMA updater started")
        else:
            logger.info("FMA updater already running.")
        self.running = True

    def anim_stop(self) -> None:
        if not self.running:
            logger.debug("anim not running")
        if self.update_fma is not None and self.fma_updater_thread is not None:
            self.update_fma.set()
            logger.debug("stopping FMA updater..")
            self.fma_updater_thread.join(FMA_UPDATE_FREQ)
            if self.fma_updater_thread.is_alive():
                logger.warning("..thread may hang..")
            self.update_fma = None
            logger.debug("..FMA updater stopped")
        else:
            logger.debug("FMA updater not running")
        if self.collect_fma is not None and self.fma_collector_thread is not None:
            self.collect_fma.set()
            logger.debug("stopping FMA collector..")
            timeout = max(FMA_SOCKET_TIMEOUT, FMA_UPDATE_FREQ)
            logger.debug(f"..asked to stop FMA collector (this may last {timeout} secs. for UDP socket to timeout)..")
            self.fma_collector_thread.join(timeout)
            if self.fma_collector_thread.is_alive():
                logger.warning("..thread may hang in socket.recvfrom()..")
            else:
                self.collect_fma = None
            logger.debug("..FMA collector stopped")
        else:
            logger.debug("FMA collector not running")
        self.running = False

    def check_boxed(self):
        """Check "boxed" datarefs to determine which texts are boxed/framed.
        They are listed as FMA#-LINE# pairs of digit. Special keyword "warn" if warning enabled.
        """
        boxed = []
        if self.button.get_dataref_value("AirbusFBW/FMAAPLeftArmedBox") == 1:
            boxed.append("22")
        if self.button.get_dataref_value("AirbusFBW/FMAAPLeftModeBox") == 1:
            boxed.append("21")
        if self.button.get_dataref_value("AirbusFBW/FMAAPRightArmedBox") == 1:
            boxed.append("32")
        if self.button.get_dataref_value("AirbusFBW/FMAAPRightModeBox") == 1:
            boxed.append("31")
        if self.button.get_dataref_value("AirbusFBW/FMAATHRModeBox") == 1:
            boxed.append("11")
        if self.button.get_dataref_value("AirbusFBW/FMAATHRboxing") == 1:
            boxed.append("12")
        if self.button.get_dataref_value("AirbusFBW/FMAATHRboxing") == 2:
            boxed.append("11")
            boxed.append("12")
        if self.button.get_dataref_value("AirbusFBW/FMATHRWarning") == 1:
            boxed.append("warn")
        # big mess:
        boxcode = self.button.get_dataref_value("AirbusFBW/FMAAPFDboxing")
        if boxcode is not None:  # can be 0-7, is it a set of binary flags?
            boxcode = int(boxcode)
            if boxcode & 1 == 1:
                boxed.append("51")
            if boxcode & 2 == 2:
                boxed.append("52")
            if boxcode & 4 == 4:
                boxed.append("53")
            # etc.
        self.boxed = set(boxed)
        logger.debug(f"boxed: {boxcode}, {self.boxed}")

    def get_fma_lines(self, idx: int = -1):
        if self.is_master_fma():
            if idx == -1:
                idx = self.fma_idx
            s = FMA_COLUMNS[idx][0]  # idx * self.text_length
            e = FMA_COLUMNS[idx][1]  # s + self.text_length
            l = e - s
            c = "1w"
            empty = c + " " * l
            lines = []
            for li in range(1, 4):
                good = empty
                for k, v in self.text.items():
                    raws = {k: v for k, v in self.text.items() if int(k[0]) == li}
                    for k, v in raws.items():
                        # normalize
                        if len(v) < FMA_LINE_LENGTH:
                            v = v + " " * (FMA_LINE_LENGTH - len(v))
                        if len(v) > FMA_LINE_LENGTH:
                            v = v[:FMA_LINE_LENGTH]
                        # extract
                        m = v[s:e]
                        if len(m) != l:
                            logger.warning(f"string '{m}' len {len(m)} has wrong size (should be {l})")
                        if (c + m) != empty:  # if good == empty and
                            good = str(li) + k[1] + m
                            lines.append(good)
            return set(lines)
        master_fma = self.get_master_fma()
        if master_fma is not None:
            return master_fma.get_fma_lines(idx=self.fma_idx)
        logger.warning(f"button {self.button.name}: fma has no master, no lines")
        return []

    def get_image_for_icon_alt(self):
        """
        Displays one FMA on one key icon, 5 keys are required for 5 FMA... (or one touchscreen, see below.)
        """
        if not self.is_updated() and self._cached is not None:
            return self._cached

        image, draw = self.double_icon(width=ICON_SIZE, height=ICON_SIZE)  # annunciator text and leds , color=(0, 0, 0, 0)
        inside = round(0.04 * image.width + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fmaconfig, "text")

        self.check_boxed()
        lines = self.get_fma_lines()
        logger.debug(f"button {self.button.name}: {lines}")
        font = self.get_font(text_font, text_size)
        w = image.width / 2
        p = "m"
        a = "center"
        idx = -1
        for text in lines:
            idx = int(text[0]) - 1  # idx + 1
            if text[2:] == (" " * (len(text) - 1)):
                continue
            h = image.height / 2
            if idx == 0:
                h = inside + text_size
            elif idx == 2:
                h = image.height - inside - text_size
            # logger.debug(f"position {(w, h)}")
            color = FMA_COLORS[text[1]]
            draw.text((w, h), text=text[2:], font=font, anchor=p + "m", align=a, fill=color)
            ref = f"{self.fma_idx+1}{idx+1}"
            if ref in self.boxed:
                draw.rectangle(
                    (
                        2 * inside,
                        h - text_size / 2,
                        ICON_SIZE - 2 * inside,
                        h + text_size / 2 + 4,
                    ),
                    outline="white",
                    width=3,
                )

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=ICON_SIZE,
            height=ICON_SIZE,
            texture_in=None,
            color_in="black",
            use_texture=False,
            who="FMA",
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        return self._cached

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        (This is currently more or less hardcoded for Elgato Streamdeck Plus touchscreen.)
        """
        if not self.all_in_one:
            return self.get_image_for_icon_alt()

        if not self.is_updated() and self._cached is not None:
            logger.debug(f"button {self.button.name}: returning cached")
            return self._cached

        # print(">>>" + "0" * 10 + "1" * 10 + "2" * 10 + "3" * 10)
        # print(">>>" + "0123456789" * 4)
        # print("\n".join([f"{k}:{v}:{len(v)}" for k, v in self.text.items()]))
        # print(">>>" + "0123456789" * 4)

        image, draw = self.double_icon(width=8 * ICON_SIZE, height=ICON_SIZE)

        inside = round(0.04 * image.height + 0.5)

        # pylint: disable=W0612
        text, text_format, text_font, text_color, text_size, text_position = self.get_text_detail(self.fmaconfig, "text")
        logger.debug(f"button {self.button.name}: is FMA master")

        icon_width = int(8 * ICON_SIZE / 5)
        loffset = 0
        has_line = False
        for i in range(FMA_COUNT - 1):
            loffset = loffset + icon_width
            if i == 1:  # second line skipped
                continue
            draw.line(((loffset, 0), (loffset, ICON_SIZE)), fill="white", width=1)
        if self.fma_label_mode > 0:
            ls = 20
            font = self.get_font(text_font, ls)
            offs = icon_width / 2
            h = inside + ls / 2
            lbl = list(FMA_LABELS.keys())
            if self.fma_label_mode == 2:
                lbl = list(FMA_LABELS.values())
            if self.fma_label_mode == 3:
                lbl = list(FMA_LABELS_ALT.values())
            for i in range(FMA_COUNT):
                draw.text(
                    (offs, h),
                    text=lbl[i],
                    font=font,
                    anchor="ms",
                    align="center",
                    fill="white",
                )
                offs = offs + icon_width

        if not self.button.sim.connected:
            logger.debug("not connected")
            draw.line(
                ((2 * icon_width, 0), (2 * icon_width, int(2 * ICON_SIZE / 3))),
                fill="white",
                width=1,
            )
            bg = self.button.deck.get_icon_background(
                name=self.button_name(),
                width=8 * ICON_SIZE,
                height=ICON_SIZE,
                texture_in=None,
                color_in="black",
                use_texture=False,
                who="FMA",
            )
            bg.alpha_composite(image)
            self._cached = bg.convert("RGB")
            self.previous_text = self.text
            logger.debug("texts updated")
            return self._cached

        loffset = 0
        for i in range(FMA_COUNT):
            lines = self.get_fma_lines(idx=i)
            logger.debug(f"button {self.button.name}: FMA {i+1}: {lines}")
            font = self.get_font(text_font, text_size)
            w = int(4 * ICON_SIZE / 5)
            p = "m"
            a = "center"
            idx = -1
            for text in lines:
                idx = int(text[0]) - 1  # idx + 1
                if text[2:] == (" " * (len(text) - 2)):
                    continue
                h = image.height / 2
                if idx == 0:
                    h = inside + text_size / 2
                elif idx == 2:
                    h = image.height - inside - text_size / 2
                    #
                    # special treatment of warning amber messages, centered across FMA 2-3, 3rd line, amber
                    # (yes, I know, they blink 5 times then stay fixed. may be one day.)
                    #
                    currline = text[:2]
                    if (i == 1 or i == 2) and currline in ["3a", "3w"]:
                        wmsg = self.text[currline][FMA_COLUMNS[1][0] : FMA_COLUMNS[2][1]].strip()
                        logger.debug(f"warning message '{wmsg}'")
                        draw.line(
                            (
                                (2 * icon_width, 0),
                                (2 * icon_width, int(2 * ICON_SIZE / 3)),
                            ),
                            fill="white",
                            width=1,
                        )
                        draw.text(
                            (2 * icon_width, h),
                            text=wmsg,
                            font=font,
                            anchor=p + "m",
                            align=a,
                            fill=FMA_COLORS[text[1]],
                        )
                        has_line = True
                        continue
                    #
                    #
                color = FMA_COLORS[text[1]]
                # logger.debug(f"added {text[2:]} @ {loffset + w}, {h}, {color}")
                draw.text(
                    (loffset + w, h),
                    text=text[2:],
                    font=font,
                    anchor=p + "m",
                    align=a,
                    fill=color,
                )
                ref = f"{i+1}{idx+1}"
                # logger.debug(ref, text)
                if ref in self.boxed:
                    if "warn" in self.boxed:
                        color = "orange"
                    else:
                        color = "white"
                    draw.rectangle(
                        (
                            loffset + 2 * inside,
                            h - text_size / 2,
                            loffset + icon_width - 2 * inside,
                            h + text_size / 2 + 4,
                        ),
                        outline=color,
                        width=3,
                    )
            loffset = loffset + icon_width

        if not has_line:
            draw.line(
                ((2 * icon_width, 0), (2 * icon_width, ICON_SIZE)),
                fill="white",
                width=1,
            )

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(
            name=self.button_name(),
            width=8 * ICON_SIZE,
            height=ICON_SIZE,
            texture_in=None,
            color_in="black",
            use_texture=False,
            who="FMA",
        )
        bg.alpha_composite(image)
        self._cached = bg.convert("RGB")
        self.previous_text = self.text
        logger.debug("texts updated")

        # with open("fma_lines.png", "wb") as im:
        #     image.save(im, format="PNG")
        #     logger.debug(f"button {self.button.name}: saved")

        return self._cached
