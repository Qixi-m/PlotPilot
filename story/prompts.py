"""各阶段 system / user 提示词模板。"""

SYSTEM_JSON_ONLY = """你是一位专业网络小说策划与写手。必须只输出合法 JSON，不要 markdown 代码围栏，不要任何解释性前后文。
JSON 须可被标准库 json.loads 直接解析。"""


def build_plan_user_prompt(
    title: str,
    premise: str,
    genre: str,
    chapter_count: int,
    words_per_chapter: int,
    style_hint: str,
) -> str:
    # 根据体裁添加针对性指导
    genre_lower = genre.lower() if genre else ""
    genre_guidance = ""

    if "都市" in genre_lower or "现代" in genre_lower:
        genre_guidance = """
【都市/现代题材特别要求】
- 注重现实感：细节要符合当代生活逻辑，避免过度戏剧化
- 人物心理：深入刻画角色内心世界，展现复杂的情感和动机
- 社会细节：融入职场、家庭、社交等真实场景
- 对话自然：使用现代口语，符合人物身份和教育背景"""
    elif "古装" in genre_lower or "历史" in genre_lower or "古代" in genre_lower:
        genre_guidance = """
【古装/历史题材特别要求】
- 历史氛围：营造时代感，注意服饰、礼仪、称谓的准确性
- 礼仪描写：展现古代社会的等级制度和行为规范
- 语言风格：对话可适度文言化，但保持可读性
- 时代背景：人物行为和价值观要符合历史背景"""
    elif "科幻" in genre_lower or "未来" in genre_lower:
        genre_guidance = """
【科幻题材特别要求】
- 世界观设定：构建完整的科技体系和社会结构
- 技术细节：科技设定要有内在逻辑，避免过于随意
- 未来感：展现科技对社会、人性的影响
- 硬核与软科幻平衡：既要有科技感，也要关注人物情感"""
    elif "玄幻" in genre_lower or "修仙" in genre_lower or "仙侠" in genre_lower:
        genre_guidance = """
【玄幻/修仙题材特别要求】
- 修炼体系：建立清晰的境界划分和修炼规则
- 境界设定：每个境界要有明确的能力差异
- 打斗场面：描写要有画面感，展现修炼成果
- 机缘与成长：设计合理的升级路径和奇遇"""
    elif "悬疑" in genre_lower or "推理" in genre_lower:
        genre_guidance = """
【悬疑/推理题材特别要求】
- 线索布局：提前埋设伏笔，确保逻辑自洽
- 节奏控制：张弛有度，适时制造悬念和反转
- 真相揭示：谜底要合理，避免强行反转
- 细节描写：关键线索要隐藏在日常细节中"""

    hint = style_hint.strip() or "节奏紧凑、对话与动作结合、避免说明文堆砌。"

    return f"""请根据以下信息生成「世界观/人物圣经」与「分章大纲」。

书名：{title}
梗概：{premise}
类型：{genre or "未指定"}
计划章数：{chapter_count}
每章目标字数约：{words_per_chapter}
风格要求：{hint}
{genre_guidance}

输出一个 JSON 对象，结构严格如下（键名一致）：
{{
  "bible": {{
    "characters": [{{"name":"角色名", "role":"主角/配角/反派", "traits":"性格特点", "arc_note":"成长弧线：从...到..."}}],
    "locations": [{{"name":"地点名", "description":"环境描述和氛围"}}],
    "timeline_notes": ["时间线要点：明确故事发生的时间跨度"],
    "style_notes": "全文叙事风格、人称、时态等约束"
  }},
  "outline": {{
    "chapters": [
      {{"id": 1, "title": "第一章标题", "one_liner": "本章一句剧情梗概"}}
    ]
  }}
}}

要求：
- chapters 必须恰好 {chapter_count} 条，id 从 1 连续递增
- 大纲结构：前20%铺垫世界观和人物，中60%推进主线冲突，后20%高潮和结局
- 每5章设置一个小高潮或转折点，保持节奏
- characters 至少 2 人，每个角色必须有明确的动机和成长弧线
- 主角必须有清晰的目标和面临的障碍
- locations 至少 1 处，描述要有氛围感
- 确保人物关系网络清晰，避免角色功能重复"""


def build_plan_revise_user_prompt(
    title: str,
    premise: str,
    genre: str,
    chapter_count: int,
    words_per_chapter: int,
    style_hint: str,
    bible_excerpt: str,
    outline_excerpt: str,
    running_summary_excerpt: str,
    premise_lock_excerpt: str,
    digest_excerpt: str,
    completed_hint: str,
) -> str:
    """基于已有圣经/大纲与创作进度，再规划或调整结构（输出同构 JSON）。"""
    hint = style_hint.strip() or "节奏紧凑、对话与动作结合、避免说明文堆砌。"
    return f"""你是一位资深网文策划编辑。本书已有初版圣经与分章大纲，且已有部分成稿与滚动摘要。
请**在尊重 manifest 梗概、已写章节事实与叙事锁定**的前提下，**修订或扩展**「圣经」与「分章大纲」，用于指导后续写作。

【书目】{title}
【梗概 manifest】{premise}
【类型】{genre or "未指定"}
【原计划章数】{chapter_count}（可微调，但若变更须在大纲中自洽说明）
【每章目标字数约】{words_per_chapter}
【风格】{hint}

【当前圣经 bible.json 摘要/节选】
{bible_excerpt}

【当前分章大纲 outline.json 摘要/节选】
{outline_excerpt}

【成稿滚动摘要（最近章节）】
{running_summary_excerpt}

【叙事侧栏 · 梗概锁定 premise_lock（若有）】
{premise_lock_excerpt}

【编务对话远期摘要节选（若有，反映已做决策）】
{digest_excerpt}

【进度提示】{completed_hint}

任务要求：
1. 分析当前结构是否仍适配后续发展；指出矛盾、缺口或节奏问题（在输出 JSON 前可简短思考，但**最终只输出 JSON**）。
2. 输出**完整** bible + outline，与初版格式一致；人物/地点可增删改，大纲章节 id 从 1 连续递增。
3. chapters 条数须与「计划章数」一致（若你调整章数，以 {chapter_count} 为默认目标，除非在 style_notes 或 timeline_notes 中明确说明调整理由）。
4. 若后文需新伏笔或新角色，在大纲 one_liner 与 bible 中体现，避免与已写摘要冲突。

输出一个 JSON 对象，结构严格如下（键名一致）：
{{
  "bible": {{
    "characters": [{{"name":"角色名", "role":"主角/配角/反派", "traits":"性格特点", "arc_note":"成长弧线"}}],
    "locations": [{{"name":"地点名", "description":"环境"}}],
    "timeline_notes": ["时间线要点"],
    "style_notes": "叙事风格、人称、禁忌等"
  }},
  "outline": {{
    "chapters": [
      {{"id": 1, "title": "第一章标题", "one_liner": "本章一句剧情"}}
    ]
  }}
}}
chapters 必须恰好 {chapter_count} 条，id 从 1 连续递增。"""


def build_beats_user_prompt(
    chapter_id: int,
    chapter_title: str,
    one_liner: str,
    bible_compact: str,
    outline_compact: str,
    previous_tail: str,
    running_summaries: str,
    target_words: int,
) -> str:
    prev = previous_tail.strip() or "（首章，无上一章）"
    sums = running_summaries.strip() or "（尚无滚动摘要）"

    # 根据章节位置判断类型，动态调整场景数量
    # 这里简化处理，实际可以从outline中获取更多信息
    scene_guidance = "scenes 至少 3-5 个，覆盖起承转合"
    if "高潮" in chapter_title or "决战" in chapter_title or "终章" in chapter_title:
        scene_guidance = "scenes 至少 5-7 个（高潮章节，场景更密集）"
    elif "过渡" in one_liner or "准备" in one_liner:
        scene_guidance = "scenes 2-3 个（过渡章节，节奏舒缓）"

    return f"""请为第 {chapter_id} 章写「场景级章纲」（beats），用于后续扩写成正文。

本章标题：{chapter_title}
本章一句：{one_liner}
目标字数约：{target_words}

【圣经与设定摘要】
{bible_compact}

【全书章纲摘要】
{outline_compact}

【上一章结尾片段】（保持衔接）
{prev}

【近几章剧情摘要】
{sums}

输出 JSON 对象（chapter_title 必须与上方「本章标题」一致）：
{{
  "chapter_id": {chapter_id},
  "chapter_title": "字符串，本章标题",
  "pov": "叙事视角说明（第一人称/第三人称全知/第三人称限知）",
  "scenes": [
    {{"summary": "本场景发生的事（包含人物动作、对话要点、情感变化）", "setting": "地点/时间/氛围"}}
  ],
  "must_resolve": "本章必须推进或解决的核心冲突/信息",
  "foreshadow_refs": ["需要呼应或埋设的伏笔关键词，可为空数组"]
}}

场景设计要求：
- {scene_guidance}
- 每个场景要有明确的目标：推进情节/展现人物/营造氛围
- 场景之间要有自然过渡，避免突兀跳转
- 重要场景要详细描述，次要场景可简略带过
- 每个场景开头简要描述环境，营造氛围
- 通过人物动作和对话展现性格，避免直接说明
- 适度使用内心独白，展现人物心理"""


def build_draft_user_prompt(
    beats_json_compact: str,
    bible_compact: str,
    outline_compact: str,
    previous_tail: str,
    running_summaries: str,
    target_words: int,
    style_notes: str,
) -> str:
    return f"""根据以下章纲写本章小说正文（中文）。

【章纲 JSON】
{beats_json_compact}

【设定摘要】
{bible_compact}

【章纲摘要】
{outline_compact}

【上一章结尾】
{previous_tail or "（首章）"}

【近几章摘要】
{running_summaries or "无"}

【风格】
{style_notes or "第三人称，过去时，叙事流畅。"}

写作要求：
1. 格式：纯正文，可在第一行用「第×章 标题」作为章首，之后直接开始正文
2. 字数：尽量接近 {target_words} 字（±15% 可接受）
3. 对话比例：对话占比约 40%，通过对话推动情节和展现人物性格
4. 环境描写：每个场景开头简要描述环境（2-3句），营造氛围
5. 人物动作：通过具体动作展现性格，避免"他很生气"这样的直接说明
6. 心理描写：适度使用内心独白（不超过20%），展现人物思考过程
7. 节奏控制：
   - 紧张场景：短句、快节奏、多动作
   - 舒缓场景：长句、慢节奏、多描写
8. 细节要求：
   - 五感描写：视觉、听觉、触觉、嗅觉、味觉
   - 具体化：用具体细节替代抽象概念
   - 避免重复：同一个动作/表情不要反复使用
9. 对话技巧：
   - 符合人物身份和性格
   - 有潜台词，不要说得太直白
   - 配合动作和表情，增强画面感
10. 禁止事项：
    - 不要输出 JSON 或列表格式
    - 不要在正文中插入作者注释
    - 避免说明文式的信息堆砌
    - 不要突然切换视角（除非章纲明确要求）

请严格按照章纲的场景顺序展开，确保每个场景都有足够的篇幅和细节。"""


def build_update_summary_user_prompt(
    chapter_id: int,
    chapter_title: str,
    chapter_excerpt_tail: str,
    existing_entries_json: str,
    max_keep: int,
) -> str:
    return f"""刚完成第 {chapter_id} 章《{chapter_title}》。请更新「滚动剧情摘要」列表，便于后续章节保持连贯。

【本章结尾片段】（供你提炼）
{chapter_excerpt_tail[:6000]}

【当前摘要列表 JSON】（数组，每项 {{"chapter_id":n,"summary":"..."}}）
{existing_entries_json}

请输出完整的新 JSON 对象：
{{"entries": [{{"chapter_id": 1, "summary": "50-120字剧情要点"}}]}}

规则：
- 为第 {chapter_id} 章新增或覆盖一条 summary。
- 仅保留最近 {max_keep} 个不同 chapter_id 的条目（按 chapter_id 升序，删掉更旧的）。
- 只输出 JSON，无其他文字。"""
