import io

from leafish.utils import nbt


def test_binary_roundtrip_compound():
    compound = {
        "name": "Steve",
        "health": nbt.NBTShort(20),
        "pos": [1.0, 64.5, -3.0],
        "inventory": [{"id": "diamond", "count": nbt.NBTByte(3)}],
        "flags": {"onGround": nbt.NBTByte(1)},
    }
    data = nbt.write_compound_typed(compound)
    parsed = nbt.read_compound(io.BytesIO(data))
    assert parsed["name"] == "Steve"
    assert isinstance(parsed["health"], int)
    assert parsed["pos"] == [1.0, 64.5, -3.0]
    assert parsed["inventory"][0]["id"] == "diamond"
    assert parsed["flags"]["onGround"] == 1


def test_named_tag_roundtrip():
    data = nbt.write_named_tag(nbt.TAG_Int, "answer", 42)
    tag_type, name, value = nbt.read_named_tag(io.BytesIO(data))
    assert (tag_type, name, value) == (nbt.TAG_Int, "answer", 42)


def test_snbt_parse():
    parsed = nbt.parse_snbt('{name:"Test",count:5b,items:[{id:"stone"}]}')
    assert parsed["name"] == "Test"
    assert parsed["count"] == 5
    assert parsed["items"][0]["id"] == "stone"


def test_snbt_format():
    text = nbt.to_snbt({"a": 1, "b": "x", "c": [1, 2]})
    assert nbt.parse_snbt(text)["a"] == 1
