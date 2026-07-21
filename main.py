# File: main.py
# ... (بداية الملف كما هي) ...

# --- Pipeline Steps Definition ---
async def processing_step(job: PageJob) -> PageJob:
    """Executes the AI extraction and validation using the user's selected persona."""
    persona_name = await settings_manager.get_persona(job.user_id)
    prompt_text = prompt_manager.get_prompt(persona_name) if persona_name else prompt_manager.get_prompt("Default Translator")
    
    raw_json = await ai_provider.extract_raw_json(job.image_bytes, job.job_id, prompt_text)
    return await validator.validate_and_update_job(job, raw_json)

async def rendering_step(job: PageJob) -> PageJob:
    """Executes the pagination and message building."""
    messages: List[str] = await paginator.paginate(job, page_num=1)
    job.message_payloads = [
        MessagePayload(page_index=i, total_pages=len(messages), text=msg)
        for i, msg in enumerate(messages)
    ]
    return job

# ... (باقي الملف كما هو) ...