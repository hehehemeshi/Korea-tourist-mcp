"""Field-level, operator-reviewed evidence. Never derive ordering policy from a menu."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Generic, Literal, TypeVar
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from . import service as s

T = TypeVar('T')
PositiveInt = Annotated[int, Field(ge=1)]
Money = Annotated[int, Field(ge=0)]

class Fact(BaseModel, Generic[T]):
    model_config = ConfigDict(extra='forbid', strict=True)
    value: T | None = None
    status: Literal['verified', 'unverified', 'unknown'] = 'unknown'
    source_url: str | None = None
    checked_at: datetime | None = None
    source_updated_at: datetime | None = None
    method: Literal['restaurant_official','direct_observation','provider_response','community','translation','government_listing','search_index','unknown'] = 'unknown'
    evidence_excerpt: str | None = Field(default=None, max_length=2000)
    attribution: str | None = None

    @field_validator('source_url')
    @classmethod
    def source_is_https(cls, value):
        if value is not None and not https_url(value):
            raise ValueError('Evidence source must be HTTPS without embedded credentials.')
        return value

    @field_validator('checked_at', 'source_updated_at')
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('Evidence timestamps require timezone offsets.')
        return value

class MenuItem(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name_ko: Fact[str] = Field(default_factory=Fact[str])
    name_original: Fact[str] = Field(default_factory=Fact[str])
    name_vi: Fact[str] = Field(default_factory=Fact[str])
    price_krw: Fact[Money] = Field(default_factory=Fact[Money])
    price_basis: Fact[Literal['per_serving','per_person','per_set']] = Field(default_factory=Fact)
    serves_people: Fact[PositiveInt] = Field(default_factory=Fact[PositiveInt])
    minimum_servings: Fact[PositiveInt] = Field(default_factory=Fact[PositiveInt])
    minimum_diners: Fact[PositiveInt] = Field(default_factory=Fact[PositiveInt])

class Policy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    minimum_servings: Fact[PositiveInt] = Field(default_factory=Fact[PositiveInt])
    one_item_per_person: Fact[bool] = Field(default_factory=Fact[bool])
    solo_allowed: Fact[bool] = Field(default_factory=Fact[bool])
    minimum_order_krw: Fact[Money] = Field(default_factory=Fact[Money])
    mandatory_extra_krw: Fact[Money] = Field(default_factory=Fact[Money])

class RestaurantEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    restaurant_id: str = Field(pattern=r'^(kakao:[0-9]+|osm:(node|way|relation):[0-9]+|source:[a-z0-9-]+)$')
    menu: list[MenuItem] = Field(default_factory=list, max_length=100)
    menu_images: list[Fact[str]] = Field(default_factory=list, max_length=20)
    policy: Policy = Field(default_factory=Policy)
    ordering_notes: list[Fact[str]] = Field(default_factory=list, max_length=30)
    opening_hours: Fact[str] = Field(default_factory=Fact[str])
    open_now: Fact[bool] = Field(default_factory=Fact[bool])
    rating_out_of_five: Fact[Annotated[float, Field(ge=0, le=5)]] = Field(default_factory=Fact)
    review_count: Fact[Money] = Field(default_factory=Fact[Money])

class Registry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    restaurants: list[RestaurantEvidence] = Field(default_factory=list, max_length=2000)


def https_url(value):
    try:
        p = urlparse(value)
        return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password
    except (ValueError, TypeError):
        return False


def fact(value=None, source=None, checked=None, reason=None):
    return dict(value=value, status='unverified' if value is not None else 'unknown',
        source_url=source if https_url(source) else None, checked_at=checked,
        source_updated_at=None, method='provider_response' if value is not None else 'unknown',
        evidence_excerpt=None, attribution=None, reason=reason)


def normalise(value, clock=None, max_age_days=30):
    clock = clock or s.now()
    if isinstance(value, Fact):
        value = value.model_dump(mode='json')
    out = {**fact(), **value}
    if out['value'] is None:
        out['status'] = 'unknown'
        return out
    if out['status'] == 'verified':
        try:
            checked = datetime.fromisoformat(out['checked_at'])
            valid = (checked.tzinfo is not None and timedelta(0) <= clock-checked <= timedelta(days=max_age_days))
        except (ValueError, TypeError):
            valid = False
        valid = valid and https_url(out['source_url']) and bool(out.get('evidence_excerpt')) and out['method'] in ('restaurant_official', 'direct_observation')
        if not valid:
            out.update(status='unverified', reason='Missing, stale or insufficient direct evidence; not safe to confirm.')
    elif out['status'] == 'unknown':
        out['status'] = 'unverified'
    return out


def load_record(restaurant_id):
    empty = RestaurantEvidence(restaurant_id=restaurant_id)
    path = os.getenv('RESTAURANT_EVIDENCE_FILE') or str(Path(__file__).parent/'data'/'restaurant_evidence.json')
    if not path:
        return empty, None
    try:
        # A broken registry must not turn unknown menu/policies into affirmative claims.
        registry = Registry.model_validate_json(Path(path).read_text())
        ids = [r.restaurant_id for r in registry.restaurants]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate restaurant IDs')
        return next((r for r in registry.restaurants if r.restaurant_id == restaurant_id), empty), None
    except (ValueError, OSError):
        return empty, 'Evidence registry invalid/unavailable; menu and ordering rules remain unknown.'


def record_payload(restaurant_id):
    record, warning = load_record(restaurant_id)
    return normalise_record(record), warning


def normalise_record(record):
    data = record.model_dump(mode='json')
    for key in ('opening_hours','rating_out_of_five','review_count'):
        data[key] = normalise(data[key])
    # A restaurant being open now changes quickly; static hours never prove it.
    data['open_now'] = normalise(data['open_now'], max_age_days=1/288)  # five minutes
    data['policy'] = {k: normalise(v) for k,v in data['policy'].items()}
    data['ordering_notes'] = [normalise(v) for v in data['ordering_notes']]
    data['menu'] = [{k:normalise(v) for k,v in item.items()} for item in data['menu']]
    images=[]
    for image in data['menu_images']:
        image=normalise(image)
        if image['value'] is not None and not https_url(image['value']):
            image=fact(reason='Unsafe/invalid image URL omitted.')
        images.append(image)
    data['menu_images']=images
    return data
