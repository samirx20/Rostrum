"""The check run after each change looks only at what changed (rostrum_core.kind: check(data, items)), and must still
catch what the whole-document check catches there: a key's owner sees a duplicate time, a list a kind it can't hold."""
from rostrum2d.kind import check


def doc():
    keys = [{"id": f"k{j}", "type": "key", "prop": "opacity", "t": j * 0.1, "v": 0.5} for j in range(3)]
    layers = [{"id": "a", "type": "text", "text": "hi", "keys": keys}, {"id": "b", "type": "text", "text": "hi", "keys": []}]
    return {"id": "root", "type": "doc", "comps": [{"id": "c", "type": "comp", "layers": layers}]}


def test_a_changed_key_is_checked_with_its_owner():
    data = doc()
    dup = {"id": "dup", "type": "key", "prop": "opacity", "t": 0.1, "v": 1}
    data["comps"][0]["layers"][0]["keys"].append(dup)
    assert check(data, [dup]) == check(data) == ["a: two opacity keys at 0.1 s"]


def test_a_changed_item_in_the_wrong_list_is_reported():
    data = doc()
    comp = {"id": "c2", "type": "comp", "layers": []}
    data["comps"][0]["layers"][1]["keys"].append(comp)
    assert check(data, [comp]) == check(data) and "can't hold a comp" in check(data, [comp])[0]
