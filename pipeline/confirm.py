"""长任务前确认与粗略 token 预估。"""


def estimate_chapter_llm_calls(num_chapters: int):
    """每章约 beats + draft + summary 共 3 次调用。"""
    return num_chapters * 3


def confirm_stage(message: str, default_yes: bool = False) -> bool:
    prompt = message.strip() + (" [Y/n]: " if default_yes else " [y/N]: ")
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return default_yes
    if default_yes:
        return ans in ("", "y", "yes")
    return ans in ("y", "yes")
