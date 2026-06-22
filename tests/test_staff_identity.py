from app.staff_identity import StaffIdentity


def test_staff_identity_recognizes_listener_explicit_id_name_and_prefix():
    identity = StaffIdentity(
        listener_user_id=9000,
        staff_user_ids={7511822833, 5361809424},
        staff_names={"Y_YY_Xankas 阿诺"},
        name_prefixes=("YY_6/9_值班号", "Y_YY"),
    )

    assert identity.is_staff(9000, "anything")
    assert identity.is_staff(7511822833, "renamed")
    assert identity.is_staff(123, "Y_YY_Xankas 阿诺")
    assert identity.is_staff(124, "YY_6/9_值班号8")
    assert not identity.is_staff(125, "customer")


def test_default_staff_ids_include_confirmed_thirteen_accounts():
    identity = StaffIdentity.source_defaults(listener_user_id=9000)

    assert identity.staff_user_ids == {
        7511822833, 6239545703, 6986253280, 7456405913, 8714311708,
        5821810621, 5361809424, 5317794797, 6728235813, 5583181496,
        7126762659, 5229932672, 5787870260,
    }
