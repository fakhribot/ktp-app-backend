import os
import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from copy import deepcopy
from datetime import datetime
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest

from google import genai
from google.genai import types
from google.genai.types import HttpRetryOptions

from dotenv import load_dotenv

today_date = datetime.today().strftime("%d-%m-%Y")

load_dotenv()

os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")

from google.genai.types import HttpRetryOptions

GEMINI_FLASH = "gemini-2.5-flash"
GEMINI_PRO = "gemini-2.5-pro"

retry_config= HttpRetryOptions(
    attempts=5,         # Maximum retry attempts
    exp_base=7,         # Delay multiplier
    initial_delay=1,    # Initial delay before first retry (in seconds)
    http_status_codes=[
        429, # Too Many Requests
        500, # Internal Server Error
        503, # Service Unavailable
        504, # Gateway Timeout
        ] # Retry on these HTTP errors
)

def validate_ktp_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """
    Callback to validate and fix KTP data using an LLM.
    Specifically enforces NIK format (16 digits) and Date format (DD-MM-YYYY).
    """
    agent_name = callback_context.agent_name
    print(f"[Callback] Validating KTP data for agent: {agent_name}")

    # 1. Extract original text (which should be JSON)
    original_text = ""
    if llm_response.content and llm_response.content.parts:
        if llm_response.content.parts[0].text:
            original_text = llm_response.content.parts[0].text
    
    if not original_text:
        return None

    # 2. Use LLM to validate and fix the data
    client = genai.Client()
    
    # Construct prompt for the validation LLM
    prompt = f"""
    Anda adalah mesin validasi presisi tinggi untuk Kartu Tanda Penduduk (KTP) Indonesia.

    Tanggal hari ini: {today_date}

    Tinjau objek JSON di bawah ini dan validasi field 'nik' dan 'birth_date' menggunakan aturan berikut:

    1. **Struktur NIK & Validasi Wilayah**:
    - Field 'nik' harus terdiri dari tepat 16 digit.
    - **Tindakan**: Gunakan Google Search untuk memverifikasi apakah 6 digit pertama
        (Provinsi, Kabupaten/Kota, Kecamatan) sesuai dengan wilayah administratif yang valid di Indonesia.
    - Digit 1-2: Provinsi | 3-4: Kabupaten/Kota | 5-6: Kecamatan.

    2. **Pemeriksaan Silang NIK & Tanggal Lahir**:
    - Digit ke-7 sampai ke-12 pada NIK merepresentasikan Tanggal Lahir dalam format [DDMMYY].
    - **Aturan Jenis Kelamin**:
        - Jika berjenis kelamin perempuan, nilai 'DD' (digit 7-8) ditambah 40.
        Contoh: tanggal lahir 15 → 55.
    - **Validasi**: Pastikan field 'birth_date' sesuai dengan 6 digit tengah NIK
        setelah memperhitungkan aturan jenis kelamin.

    3. **Validasi Usia**:
    - Hitung usia berdasarkan 'birth_date' dan Tanggal Hari Ini.
    - **Aturan**: Jika usia < 17 tahun, maka data dinyatakan **TIDAK VALID**
        dan harus ditandai sebagai invalid pada hasil JSON.

    4. **Format Data**:
    - 'nik': String, 16 digit, tanpa spasi atau karakter khusus.
    - 'birth_date': String dalam format 'YYYY-MM-DD'.
    - Jika kode wilayah NIK, logika tanggal, atau usia tidak valid,
        tandai atau perbaiki berdasarkan sumber paling tepercaya (hasil pencarian).

    Input JSON:
    {original_text}

    Return ONLY the valid JSON string, no markdown formatting.
    """

    tools = [types.Tool(google_search=types.GoogleSearch())]


    config = types.GenerateContentConfig(
        tools=tools,
        temperature=0.1 
    )

    try:        
        response = client.models.generate_content(
            model=GEMINI_FLASH,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=config
        )

        if response and response.text:
            validated_json = response.text.strip()
            
            # Optional: Strip markdown code blocks if the LLM added them
            if validated_json.startswith("```"):
                validated_json = validated_json.strip("`").replace("json\n", "").strip()

            print(f"[Callback] KTP Data validated and formatted.")
            
            # 3. Return modified response
            modified_parts = [deepcopy(part) for part in llm_response.content.parts]
            modified_parts[0].text = validated_json

            return LlmResponse(
                content=types.Content(role="model", parts=modified_parts),
                grounding_metadata=llm_response.grounding_metadata
            )
    except Exception as e:
        print(f"[Callback] Error during KTP validation: {e}")
        return None 

    return None

class KTPExtractionResult(BaseModel):
    nik: str = Field(description="Nomor Induk Kependudukan (16 digits)")
    full_name: str = Field(description="Nama lengkap (Full Name)")
    birth_place: str = Field(description="Tempat lahir (Place of Birth)")
    birth_date: str = Field(description="Tanggal lahir (Date of Birth) in YYYY-MM-DD format")
    gender: str = Field(description="Jenis kelamin (Laki-laki/Perempuan)")
    blood_type: str = Field(description="Golongan darah (Blood Type) e.g., A, B, O, AB, or -")
    address: str = Field(description="Alamat lengkap (Full Address)")
    rt_rw: str = Field(description="RT/RW")
    village_kelurahan: str = Field(description="Kelurahan/Desa")
    district_kecamatan: str = Field(description="Kecamatan")
    religion: str = Field(description="Agama (Religion)")
    marital_status: str = Field(description="Status perkawinan (Marital Status)")
    occupation: str = Field(description="Pekerjaan (Occupation)")
    citizenship: str = Field(description="Kewarganegaraan (Citizenship) e.g., WNI")
    expiry_date: str = Field(description="Berlaku hingga (Expiry Date) or 'SEUMUR HIDUP'")

extraction_agent = LlmAgent(
    model=Gemini(
        model=GEMINI_FLASH,
        retry_options=retry_config
    ),
    name='extraction_agent',
    description='Asisten yang membantu mengekstrak data identitas terstruktur dari dokumen KTP Indonesia.',
    instruction=(
    "Anda adalah asisten OCR dan ekstraksi data yang ahli untuk Kartu Tanda Penduduk (KTP) Indonesia. "
    "Tujuan Anda adalah mengekstrak field tertentu dari gambar atau teks KTP yang diberikan.\n\n"
    "1. Analisis dokumen KTP yang disediakan.\n"
    "2. Ekstrak field yang didefinisikan dalam skema output secara akurat.\n"
    "3. **Tempat & Tanggal Lahir:** Di KTP, ini tertulis dalam satu baris (contoh: 'JAKARTA, 17-08-1945').\n"
        "   - Anda WAJIB memisahkan teks ini.\n"
        "   - Teks sebelum koma/angka adalah 'birth_place'.\n"
        "   - Angka tanggal (DD-MM-YYYY) adalah 'birth_date'.\n"
    "4. Pastikan tanggal diformat sebagai YYYY-MM-DD jika memungkinkan.\n"
    "5. Isi dengan NULL jika informasi tidak tersedia atau tidak dapat diekstrak.\n"
    "6. Field expiry_date harus SELALU diisi dengan 'SEUMUR HIDUP'.\n"
    "7. Kembalikan HANYA objek JSON akhir yang sesuai dengan skema KTPExtractionResult."
),
    output_schema=KTPExtractionResult,
    output_key='extraction_result',
    after_model_callback=validate_ktp_callback
)

root_agent = extraction_agent

session_service = InMemorySessionService()

async def process_document(file_bytes: bytes, mime_type: str, user_id: str = "system"):
    """
    Runs the ADK agent to extract data from the provided file bytes.
    """
    app_name = "ktp_backend_ocr"
    session_id = f"{user_id}-{int(time.time())}"

    # Ensure session exists
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)

    runner = Runner(agent=extraction_agent, app_name=app_name, session_service=session_service)

    # Construct the prompt
    prompt_text = "Extract informasi identitas dari gambar KTP ini."
    parts = [types.Part(text=prompt_text)]
    
    if file_bytes and mime_type:
        file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        parts.append(file_part)

    content = types.Content(role='user', parts=parts)

    # Run Agent
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)

    final_json = {}
    
    async for event in events:
        if event.is_final_response():
            try:
                import json
                text_response = event.content.parts[0].text
                # Clean markdown code blocks if present
                if "```json" in text_response:
                    text_response = text_response.split("```json")[1].split("```")[0]
                elif "```" in text_response:
                    text_response = text_response.split("```")[1].split("```")[0]
                
                final_json = json.loads(text_response)
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                final_json = {"error": "Failed to parse agent response"}

    return final_json