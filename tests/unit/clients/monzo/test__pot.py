"""Unit Tests for `wg_utilities.clients.monzo.Pot`."""

from __future__ import annotations

from datetime import datetime

from wg_utilities.clients.monzo import Pot


def test_instantiation() -> None:
    """Test `Pot` instantiation."""

    pot = Pot(
        json={
            "id": "test_pot_id",
            "name": "Pot Name",
            "style": "",
            "balance": 50,
            "currency": "GBP",
            "type": "default",
            "product_id": "default",
            "current_account_id": "test_account_id",
            "cover_image_url": "https://via.placeholder.com/200x100",
            "isa_wrapper": "",
            "round_up": True,
            "round_up_multiplier": None,
            "is_tax_pot": False,
            "created": "2020-01-01T01:00:00.000Z",
            "updated": "2020-01-01T02:00:00.000Z",
            "deleted": False,
            "locked": False,
            "available_for_bills": True,
            "has_virtual_cards": False,
            "goal_amount": None,
            "charity_id": None,
        }
    )

    assert isinstance(pot, Pot)
    assert pot.json == {
        "id": "test_pot_id",
        "name": "Pot Name",
        "style": "",
        "balance": 50,
        "currency": "GBP",
        "type": "default",
        "product_id": "default",
        "current_account_id": "test_account_id",
        "cover_image_url": "https://via.placeholder.com/200x100",
        "isa_wrapper": "",
        "round_up": True,
        "round_up_multiplier": None,
        "is_tax_pot": False,
        "created": "2020-01-01T01:00:00.000Z",
        "updated": "2020-01-01T02:00:00.000Z",
        "deleted": False,
        "locked": False,
        "available_for_bills": True,
        "has_virtual_cards": False,
        "goal_amount": None,
        "charity_id": None,
    }


def test_available_for_bills_property(monzo_pot: Pot) -> None:
    """Test the `available_for_bills` property returns the correct value."""
    assert monzo_pot.available_for_bills is True
    monzo_pot.json["available_for_bills"] = False
    assert monzo_pot.available_for_bills is False


def test_balance_property(monzo_pot: Pot) -> None:
    """Test the `balance` property returns the correct value."""
    assert monzo_pot.balance == 50
    monzo_pot.json["balance"] = 55
    assert monzo_pot.balance == 55


def test_charity_id_property(monzo_pot: Pot) -> None:
    """Test the `charity_id` property returns the correct value."""
    assert monzo_pot.charity_id is None
    monzo_pot.json["charity_id"] = "test_charity_id"
    assert monzo_pot.charity_id == "test_charity_id"


def test_cover_image_url_property(monzo_pot: Pot) -> None:
    """Test the `cover_image_url` property returns the correct value."""
    assert monzo_pot.cover_image_url == "https://via.placeholder.com/200x100"
    monzo_pot.json["cover_image_url"] = "https://via.placeholder.com/200x200"
    assert monzo_pot.cover_image_url == "https://via.placeholder.com/200x200"


def test_created_datetime_property(monzo_pot: Pot) -> None:
    """Test the `created_datetime` property returns the correct value."""
    assert monzo_pot.created_datetime == datetime(2020, 1, 1, 1)
    monzo_pot.json["created"] = "2020-01-01T02:00:00.000Z"
    assert monzo_pot.created_datetime == datetime(2020, 1, 1, 2)


def test_currency_property(monzo_pot: Pot) -> None:
    """Test the `currency` property returns the correct value."""
    assert monzo_pot.currency == "GBP"
    monzo_pot.json["currency"] = "EUR"
    assert monzo_pot.currency == "EUR"


def test_current_account_id_property(monzo_pot: Pot) -> None:
    """Test the `current_account_id` property returns the correct value."""
    assert monzo_pot.current_account_id == "test_account_id"
    monzo_pot.json["current_account_id"] = "test_account_id_2"
    assert monzo_pot.current_account_id == "test_account_id_2"


def test_deleted_property(monzo_pot: Pot) -> None:
    """Test the `deleted` property returns the correct value."""
    assert monzo_pot.deleted is False
    monzo_pot.json["deleted"] = True
    assert monzo_pot.deleted is True


def test_goal_amount_property(monzo_pot: Pot) -> None:
    """Test the `goal_amount` property returns the correct value."""
    assert monzo_pot.goal_amount is None
    monzo_pot.json["goal_amount"] = 1234
    assert monzo_pot.goal_amount == 1234


def test_has_virtual_cards_property(monzo_pot: Pot) -> None:
    """Test the `has_virtual_cards` property returns the correct value."""
    assert monzo_pot.has_virtual_cards is False
    monzo_pot.json["has_virtual_cards"] = True
    assert monzo_pot.has_virtual_cards is True


def test_id_property(monzo_pot: Pot) -> None:
    """Test the `id` property returns the correct value."""
    assert monzo_pot.id == "test_pot_id"
    monzo_pot.json["id"] = "test_pot_id_2"
    assert monzo_pot.id == "test_pot_id_2"


def test_is_tax_pot_property(monzo_pot: Pot) -> None:
    """Test the `is_tax_pot` property returns the correct value."""
    assert monzo_pot.is_tax_pot is False
    monzo_pot.json["is_tax_pot"] = True
    assert monzo_pot.is_tax_pot is True


def test_isa_wrapper_property(monzo_pot: Pot) -> None:
    """Test the `isa_wrapper` property returns the correct value."""
    assert monzo_pot.isa_wrapper == ""
    monzo_pot.json["isa_wrapper"] = "something"
    assert monzo_pot.isa_wrapper == "something"


def test_locked_property(monzo_pot: Pot) -> None:
    """Test the `locked` property returns the correct value."""
    assert monzo_pot.locked is False
    monzo_pot.json["locked"] = True
    assert monzo_pot.locked is True


def test_name_property(monzo_pot: Pot) -> None:
    """Test the `name` property returns the correct value."""
    assert monzo_pot.name == "Pot Name"
    monzo_pot.json["name"] = "New Pot Name"
    assert monzo_pot.name == "New Pot Name"


def test_product_id_property(monzo_pot: Pot) -> None:
    """Test the `product_id` property returns the correct value."""
    assert monzo_pot.product_id == "default"
    monzo_pot.json["product_id"] = "premium"
    assert monzo_pot.product_id == "premium"


def test_round_up_property(monzo_pot: Pot) -> None:
    """Test the `round_up` property returns the correct value."""
    assert monzo_pot.round_up is True
    monzo_pot.json["round_up"] = False
    assert monzo_pot.round_up is False


def test_round_up_multiplier_property(monzo_pot: Pot) -> None:
    """Test the `round_up_multiplier` property returns the correct value."""
    assert monzo_pot.round_up_multiplier is None
    monzo_pot.json["round_up_multiplier"] = 2
    assert monzo_pot.round_up_multiplier == 2


def test_style_property(monzo_pot: Pot) -> None:
    """Test the `style` property returns the correct value."""
    assert monzo_pot.style == ""
    monzo_pot.json["style"] = "fancy"
    assert monzo_pot.style == "fancy"


def test_type_property(monzo_pot: Pot) -> None:
    """Test the `type` property returns the correct value."""
    assert monzo_pot.type == "default"
    monzo_pot.json["type"] = "savings"
    assert monzo_pot.type == "savings"


def test_updated_datetime_property(monzo_pot: Pot) -> None:
    """Test the `updated_datetime` property returns the correct value."""
    assert monzo_pot.updated_datetime == datetime(2020, 1, 1, 2)
    monzo_pot.json["updated"] = "2020-01-01T03:00:00.000Z"
    assert monzo_pot.updated_datetime == datetime(2020, 1, 1, 3)
