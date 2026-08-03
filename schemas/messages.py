"""
Pydantic schemas shared across all agents in the AI Travel Planner.
"""
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import date, datetime, timezone


class AgentID(str, Enum):
    ORCHESTRATOR = "orchestrator"
    FLIGHT = "flight_agent"
    HOTEL = "hotel_agent"
    ACTIVITY = "activity_agent"
    PRICING = "pricing_agent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REALLOCATION = "needs_reallocation"


class AgentMessage(BaseModel):
    """Envelope every agent uses to report back to the orchestrator's state."""
    agent_id: AgentID
    task_type: str
    status: TaskStatus
    payload: dict
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    budget_used: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---- Domain payloads ----

class FlightOption(BaseModel):
    airline: str
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    price: float
    stops: int = 0


class HotelOption(BaseModel):
    name: str
    area: str
    price_per_night: float
    total_price: float
    rating: Optional[float] = None
    amenities: list[str] = []


class ActivitySuggestion(BaseModel):
    name: str
    category: str
    day: int
    estimated_cost: float
    duration_hours: float


BudgetCategory = Literal["flight", "hotel", "activity"]


class BudgetLine(BaseModel):
    category: BudgetCategory
    allocated: float
    actual: float

    @property
    def variance(self) -> float:
        """Positive = over allocated ceiling, negative = under."""
        return self.actual - self.allocated


class ReallocationInstruction(BaseModel):
    """Emitted by the Pricing Agent when a category is over budget."""
    target_agent: AgentID
    category: BudgetCategory
    new_ceiling: float
    reason: str


# ---- API request/response ----

class TripRequest(BaseModel):
    destination: str
    origin: str
    start_date: date
    end_date: date
    budget: float
    interests: list[str]
    currency: str = "INR"


class Itinerary(BaseModel):
    trip_request: TripRequest
    flight: Optional[FlightOption] = None
    hotel: Optional[HotelOption] = None
    activities: list[ActivitySuggestion] = []
    budget_breakdown: list[BudgetLine] = []
    total_cost: float = 0.0
    negotiation_rounds: int = 0
    best_effort: bool = False  # True if we hit max_negotiation_rounds still over budget
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
