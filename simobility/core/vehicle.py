from enum import Enum
from typing import Dict, Optional
import logging
from transitions.core import EventData
from .state_machine import StateMachine
from .position import Position
from .vehicle_engine import VehicleEngine


class States(Enum):

    offline = "offline"

    idling = "idling"
    # use moving_to instead of simply moving
    # since Vehicle already has is_moving property
    moving_to = "moving"


# format: [trigger, source, destination]
state_transitions = [
    ["set_idling", [States.offline, States.moving_to], States.idling],
    ["set_offline", States.idling, States.offline],
    ["set_moving_to", States.idling, States.moving_to],
]


class StopReasons(Enum):
    """Reasons why vehicle stops"""

    arrived = "arrived"
    change = "change_dest"
    unknown = "unknown"
    stop = "stop"


class Vehicle(StateMachine):

    """
    Functions autogenerated by StateMachine

    vehicle.is_<STATE>()
    vehicle.set_<STATE>()

    vehicle.is_offline()
    vehicle.set_offline()

    vehicle.is_idling()
    vehicle.set_idling()

    vehicle.is_moving_to()
    vehicle.set_moving_to()
    """

    def __init__(self, clock, vehicle_id: str = None):
        states = [s for s in States]
        super().__init__(
            clock, state_transitions, states, States.offline, object_id=vehicle_id
        )

        self.engine: Optional[VehicleEngine] = None

        self.context: Dict = {}

    @property
    def position(self) -> Optional[Position]:
        """Current position of the vehicle. Returns None if engine is not installed
        """
        if self.engine is not None:
            return self.engine.current_position

    @property
    def is_moving(self) -> bool:
        return self.engine is not None and self.engine.is_moving()

    @property
    def destination(self) -> Optional[Position]:
        """If vehicle is moving return the destination"""
        if self.engine:
            return self.engine.destination

    def move_to(self, destination: Position, **context):
        if not self.engine:
            raise Exception("Cannot move vehicle without engine")
 
        elif self.engine.is_moving():
            # if vehicle already moving to the same destination do nothing
            if destination != self.destination:
                # stop current trip
                self.stop(StopReasons.change, context)
                # change the destination
                self.engine.start_move(destination)
            # else:
            # logging.warning('Move to the same destination')
        else:
            self.engine.start_move(destination)

        if self.engine.is_moving() and self.is_idling():
            self.context = context
            self.set_moving_to(**context)

    def stop(self, stop_reason: Enum = None, **context):
        if not self.engine:
            raise Exception("Cannot stop vehicle without engine")

        if self.is_idling():
            logging.warning("Stop idling vehicle")
        else:
            if not stop_reason:
                stop_reason = StopReasons.unknown

            context = context or self.context
            self.set_idling(stop=stop_reason.value, **context)
            self.context = {}

            self.engine.end_move()

    def step(self):
        if not self.engine:
            raise Exception("Cannot step vehicle without engine")

        elif self.is_moving_to() and not self.engine.is_moving():
            # vehicle has arrived to the destination
            self.stop(StopReasons.arrived, **self.context)

        elif self.is_idling() and self.engine.is_moving():
            logging.warning(
                f"Engine is moving, vehicle {self.id} is idling at {self.position}"
            )

            raise Exception("Undefined state")

    def install_engine(self, engine: VehicleEngine):
        """Only after engine is installed vehicle changes its state to idling"""

        if self.engine:
            raise Exception("Engine is already installed")

        self.engine = engine
        self.set_idling(**self.context)

    def on_state_changed(self, event: EventData):
        """Called on each state change"""

        # TODO: check if kwargs already have keys
        event.kwargs["position"] = self.position.to_dict()

        route = self.engine.route
        if route:
            event.kwargs["origin"] = route.origin.to_dict()
            event.kwargs["destination"] = route.destination.to_dict()

            # distance in km
            event.kwargs["traveled_distance"] = round(
                route.traveled_distance(self.engine.now), 3
            )

        super().on_state_changed(event)
