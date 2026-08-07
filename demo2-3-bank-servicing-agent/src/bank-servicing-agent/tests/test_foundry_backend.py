from agent_framework import AgentResponse, Content, Message

from bank_servicing_agent.foundry_backend import _tool_activity


def test_tool_activity_requires_a_successful_matching_result() -> None:
    response = AgentResponse(
        messages=[
            Message(
                "assistant",
                [
                    Content.from_function_call(
                        call_id="fabric-call",
                        name="fabric-iq-acmebank___DataAgent_AcmeBankServicingAgent",
                    ),
                    Content.from_function_call(
                        call_id="work-call",
                        name="workiq___ask",
                    ),
                ],
            ),
            Message(
                "tool",
                [
                    Content.from_function_result(
                        call_id="fabric-call",
                        result={"answer": "Account evidence"},
                    ),
                    Content.from_function_result(
                        call_id="work-call",
                        result=None,
                        exception="Work IQ failed",
                    ),
                ],
            ),
        ]
    )

    queried, grounded = _tool_activity(response)

    assert queried == ("Fabric IQ", "Work IQ")
    assert grounded == ("Fabric IQ",)
