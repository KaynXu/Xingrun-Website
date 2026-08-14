import unittest

from class_commentary_memory_privacy import (
    contains_class_commentary_private_information,
    contains_class_commentary_roster_name,
    normalize_class_commentary_roster_name,
    validate_class_commentary_memory_privacy,
)


class ClassCommentaryMemoryPrivacyTest(unittest.TestCase):
    def test_phone_numbers_are_detected(self):
        for value in ("13800138000", "请联系 13800138000。", "电话:13800138000"):
            self.assertTrue(
                contains_class_commentary_private_information(value), value
            )

    def test_spaced_phone_numbers_are_a_known_detection_gap(self):
        # The phone regex requires contiguous digits; spaced formats like
        # "138 0013 8000" currently fall through. Documented gap, not a
        # regression: tightening it would change which memories are accepted.
        self.assertFalse(
            contains_class_commentary_private_information("电话 138 0013 8000")
        )

    def test_phone_like_numbers_outside_13x_19x_are_not_detected(self):
        for value in ("11001100110", "12345678901", "学号 202600013"):
            self.assertFalse(
                contains_class_commentary_private_information(value), value
            )

    def test_email_addresses_are_detected(self):
        self.assertTrue(
            contains_class_commentary_private_information("发到 xiaolin@example.com 即可")
        )

    def test_identifier_sequences_are_detected(self):
        self.assertTrue(
            contains_class_commentary_private_information("身份证 110101199003078515")
        )

    def test_contact_keywords_are_detected(self):
        for value in ("微信号：xiaolin123", "加我 wechat 私聊", "留一下手机号"):
            self.assertTrue(
                contains_class_commentary_private_information(value), value
            )

    def test_address_patterns_are_detected(self):
        for value in ("中山路100号", "住在朝阳小区 3 栋 502 室", "幸福街 12 号"):
            self.assertTrue(
                contains_class_commentary_private_information(value), value
            )

    def test_plain_classroom_text_is_not_private(self):
        for value in ("二次函数图像目前较薄弱。", "小林这次分类讨论漏了边界条件。"):
            self.assertFalse(
                contains_class_commentary_private_information(value), value
            )

    def test_roster_name_detection_ignores_spaces_and_case(self):
        self.assertTrue(
            contains_class_commentary_roster_name(
                ["课上 WANG  XIAO 被点名"], ["wangxiao"]
            )
        )
        self.assertEqual(normalize_class_commentary_roster_name(" WANG  Xiao "), "wangxiao")

    def test_roster_name_detection_is_substring_based(self):
        self.assertTrue(
            contains_class_commentary_roster_name(["小林同学的作业"], ["小林"])
        )
        self.assertFalse(
            contains_class_commentary_roster_name(["小周的作业"], ["小林"])
        )

    def test_validation_rejects_private_information_or_roster_names(self):
        with self.assertRaises(ValueError):
            validate_class_commentary_memory_privacy(
                memory_text="表现良好",
                support=["电话 13800138000"],
                roster_names=[],
            )
        with self.assertRaises(ValueError):
            validate_class_commentary_memory_privacy(
                memory_text="小林表现良好",
                support=["证据"],
                roster_names=["小林"],
            )

    def test_validation_accepts_clean_memories(self):
        validate_class_commentary_memory_privacy(
            memory_text="二次函数分类讨论仍会漏边界",
            support=["课后练习正确率提升"],
            roster_names=["小林", "小周"],
        )


if __name__ == "__main__":
    unittest.main()
