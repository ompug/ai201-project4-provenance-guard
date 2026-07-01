def build_transparency_label(attribution: str, verified: bool = False) -> str:
    if attribution == "likely_ai":
        base_label = (
            "Likely created with AI assistance. Multiple checks agree, and we are "
            "confident in this assessment."
        )
    elif attribution == "likely_human":
        base_label = (
            "Likely written by a person. Multiple checks agree, and we are confident "
            "in this assessment."
        )
    else:
        base_label = (
            "Origin unclear. We could not confidently tell whether a person or AI wrote "
            "this. The creator can request a human review."
        )

    if verified:
        return f"Verified human creator - {base_label}"

    return base_label
