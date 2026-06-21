import pytest
from app.models import CalculationResult, FinancialData, ChatMessage, ChatRecord, ChatRequest


class TestFinancialData:
    def test_defaults(self):
        data = FinancialData()
        assert data.goal_price is None
        assert data.monthly_income is None
        assert data.current_savings is None
        assert data.extra_income is None
        assert data.current_debts is None
        assert data.goals == []

    def test_non_negative_validation(self):
        with pytest.raises(ValueError):
            FinancialData(goal_price=-100)

    def test_full_data(self):
        data = FinancialData(
            goal_price=50000.0,
            monthly_income=10000.0,
            monthly_expenses=5000.0,
            current_savings=20000.0,
            extra_income=2000.0,
        )
        assert data.goal_price == 50000.0
        assert data.goals == []

    def test_all_numbers_field(self):
        data = FinancialData(all_numbers=[100, 200, 300])
        assert data.all_numbers == [100, 200, 300]

    def test_segments_field(self):
        data = FinancialData(segments=[{"text": "earn 5000", "classifications": [{"field": "monthly_income", "value": 5000}]}])
        assert len(data.segments) == 1
        assert data.segments[0]["text"] == "earn 5000"


class TestChatMessage:
    def test_auto_id_and_timestamp(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.id is not None
        assert msg.created_at is not None

    def test_with_extracted_data(self):
        data = FinancialData(goal_price=50000.0)
        msg = ChatMessage(role="assistant", content="result", extracted_data=data)
        assert msg.extracted_data.goal_price == 50000.0


class TestChatRecord:
    def test_full_record(self):
        data = FinancialData(goal_price=50000.0)
        user_msg = ChatMessage(role="user", content="test")
        assistant_msg = ChatMessage(role="assistant", content="response")
        record = ChatRecord(
            user_id="user1",
            conversation_id="conv1",
            user_message=user_msg,
            assistant_message=assistant_msg,
            extracted_data=data,
            calculation=CalculationResult(
                net_monthly_savings=0,
                remaining=0,
                months=0,
                raw_months=0,
                duration_display="test",
                is_achievable=True,
                suggestions=[],
            ),
        )
        assert record.user_id == "user1"
        assert record.conversation_id == "conv1"


class TestChatRequest:
    def test_minimal(self):
        req = ChatRequest(message="hello")
        assert req.message == "hello"
        assert req.user_id == "default-user"
        assert req.conversation_id is None

    def test_custom_user(self):
        req = ChatRequest(message="hello", user_id="custom")
        assert req.user_id == "custom"