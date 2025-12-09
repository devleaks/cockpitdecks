"""An Activity is something that happened in the simulator  (or elsewhere)"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List


from cockpitdecks import yaml

logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)  # To see when simulator_variable are updated
# logger.setLevel(logging.DEBUG)


class Activity:
    """An activity is something that happened in the simulator."""

    def __init__(self, name: str, value: Any | None = None):
        self.name = name
        self.value: Any | None = value
        self.listeners: List[ActivityListener] = []  # buttons using this simulator_variable, will get notified if changes.
        self._creator: str | None = None

    def activate(self, value, cascade: bool = True):
        # For now, activity only reports it occured.
        # If part of a Observable, the observable will take care
        # of carrying out the associated "actions".
        # Here, we only inform that it occured.
        logger.info(f"{self.name} activating value={value}, cascade={cascade}")
        self.value = value
        if cascade:
            self.notify()

    # ################################
    # Listeners
    #
    def add_listener(self, obj):
        if not isinstance(obj, ActivityListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj not in self.listeners:
            self.listeners.append(obj)
        logger.debug(f"{self.name} added listener ({len(self.listeners)})")

    def remove_listener(self, obj):
        if not isinstance(obj, ActivityListener):
            logger.warning(f"{self.name} not a listener {obj}")
        if obj in self.listeners:
            self.listeners.remove(obj)
        logger.debug(f"{self.name} removed listener ({len(self.listeners)})")

    def notify(self):
        for lsnr in self.listeners:
            lsnr.activity_received(self)
            logger.debug(f"{self.name}: notified {lsnr.name}")


class ActivityListener(ABC):
    """A VariableListener is an entity that is interested in being notified
    when a data changes.
    """

    def __init__(self, name: str = "abstract-activity-listener"):
        self.al_name = name

    @abstractmethod
    def activity_received(self, activity: Activity):
        raise NotImplementedError


class ActivityFactory(ABC):
    """A VariableFactory has a function to generate variable for its own use."""

    @abstractmethod
    def activity_factory(self, name: str, creator: str | None = None) -> Activity:
        raise NotImplementedError


class ActivityDatabase:
    """Container for all activities."""

    def __init__(self) -> None:
        self.database: Dict[str, Activity] = {}

    def register(self, activity: Activity) -> Activity:
        if activity.name is None:
            logger.warning(f"invalid activity name {activity.name}, not stored")
            return activity
        if activity.name not in self.database:
            self.database[activity.name] = activity
        else:
            logger.debug(f"activity {activity.name} already registered")
        return activity

    def exists(self, name: str) -> bool:
        return name in self.database

    def get(self, name: str) -> Activity | None:
        if not self.exists(name):
            logger.debug(f"activity {name} not found")
        return self.database.get(name)

    def value_of(self, name: str, default: Any = None) -> Any | None:
        v = self.get(name)
        if v is None:
            logger.warning(f"{name} not found")
            return None
        return v.current_value if v.current_value is not None else default

    def show_all(self, word: str = None):
        for k in self.database:
            if word is None or word in k:
                logger.debug(f"{k} = {self.value_of(k)}")

    def remove_all_simulator_activitys(self):
        to_delete = []
        for d in self.database:
            if Activity.may_be_non_internal_activity(d):  # type(activity) is Dataref
                to_delete.append(d)
        for d in to_delete:
            self.database.pop(d)

    def dump(self, filename: str = "activity-database-dump.yaml"):
        drefs = {d.name: d.value for d in self.database.values()}  #  if d.is_internal
        with open(filename, "w") as fp:
            yaml.dump(drefs, fp)
            logger.debug(f"activities saved in {filename} file")
