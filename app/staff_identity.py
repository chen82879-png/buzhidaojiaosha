from dataclasses import dataclass


SOURCE_STAFF_IDS = {
    7511822833, 6239545703, 6986253280, 7456405913, 8714311708,
    5821810621, 5361809424, 5317794797, 6728235813, 5583181496,
    7126762659, 5229932672, 5787870260,
}

SOURCE_STAFF_NAMES = {
    "Y_YY_grybuges", "Y_YY_Xankas 阿诺", "Y_YY_Belxiron",
    "Y_YY_Zillmann 阿布", "Y_YY_ARATAKITO", "Y_YY_wladyslaw",
    "YY_6/9_值班号2【拒绝私聊】", "YY_6/9_值班号3【拒绝私聊】",
    "YY_6/9_值班号6【拒绝私聊】", "YY_6/9_值班号⑤",
    "YY_6/9_值班号7【拒绝私聊】", "YY_6/9_值班号➊",
    "YY_6/9_值班号4【拒绝私聊】",
}


@dataclass(frozen=True)
class StaffIdentity:
    listener_user_id: int = 0
    staff_user_ids: set[int] | None = None
    staff_names: set[str] | None = None
    name_prefixes: tuple[str, ...] = ("YY_6/9_值班号", "Y_YY")

    def __post_init__(self):
        object.__setattr__(self, "staff_user_ids", set(self.staff_user_ids or ()))
        object.__setattr__(self, "staff_names", set(self.staff_names or ()))

    @classmethod
    def source_defaults(cls, listener_user_id: int = 0, extra_ids=()):
        return cls(
            listener_user_id=listener_user_id,
            staff_user_ids=SOURCE_STAFF_IDS | {int(value) for value in extra_ids},
            staff_names=SOURCE_STAFF_NAMES,
        )

    def is_staff(self, user_id: int, display_name: str = "") -> bool:
        name = str(display_name or "").strip()
        return bool(
            (self.listener_user_id and user_id == self.listener_user_id)
            or user_id in self.staff_user_ids
            or name in self.staff_names
            or any(name.startswith(prefix) for prefix in self.name_prefixes)
        )
