import discord
from discord.ext import commands
from discord import app_commands
import openai
import os
import json
import aiofiles
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)

history_folder = "conversation_history"
user_memory_file = "user_memory.json"

# 폴더 및 파일 생성
if not os.path.exists(history_folder):
    os.makedirs(history_folder)

if not os.path.exists(user_memory_file):
    with open(user_memory_file, 'w', encoding='utf-8') as f:
        json.dump({}, f)  # 사용자 정보를 저장할 파일 초기화

# 사용자별 메모리
user_memory = {}

def load_user_memory():
    """봇 시작 시 사용자 메모리 로드"""
    global user_memory
    if os.path.exists(user_memory_file):
        with open(user_memory_file, "r", encoding="utf-8") as file:
            user_memory = json.load(file)

def save_user_memory():
    """사용자 메모리를 저장 (대화 발생 시 호출)"""
    with open(user_memory_file, "w", encoding="utf-8") as file:
        json.dump(user_memory, file, ensure_ascii=False, indent=4)
        
async def save_message(channel_id, text):
    """채널별 대화 내용을 저장하는 함수"""
    file_path = os.path.join(history_folder, f"{channel_id}.txt")
    async with aiofiles.open(file_path, "a", encoding="utf-8") as file:
        await file.write(f"{text}\n")

@bot.event
async def on_ready():
    print(f"✅ 봇 온라인: {bot.user}")
    try:
        await bot.tree.sync()  # 슬래시 명령어 동기화
        print("✅ 슬래시 명령어 동기화 완료!")
    except Exception as e:
        print(f"❌ 명령어 동기화 오류: {e}")
    load_user_memory()

async def save_message(channel_id, text):
    """대화 내용을 올바른 순서로 저장"""
    file_path = os.path.join(history_folder, f"{channel_id}.txt")
    async with aiofiles.open(file_path, "a", encoding="utf-8") as file:
        await file.write(f"{text}\n")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        if not message.content.startswith(bot.command_prefix) and ":대화 내용 요약:" not in message.content:
            await save_message(message.channel.id, f"{message.author}: {message.content}")
        return
    
        # 봇이 보낸 메시지에 대한 답장일 경우
    if message.reference and message.reference.message_id:
        referenced_message = await message.channel.fetch_message(message.reference.message_id)
        print(f"📩 [봇 메시지에 대한 답장 감지] {message.author}: {message.content}")
        response = generate_ai_response(message.content, message.author.id)
        if response:
            await message.reply(response, mention_author=False)  # 공개 답장
            print(f"💬 [응답] {bot.user}: {response}")
        else:
            print("❌ [오류] AI 응답을 생성하지 못함")

    # 트리거 단어 확인 후 응답
    trigger_phrases = [":ai.response", ":어떻게생각해?", ":howdoyouthink"]
    if any(message.content.strip().endswith(trigger) for trigger in trigger_phrases):
        print(f"📩 [트리거 감지] {message.author}: {message.content}")
        response = generate_ai_response(message.content, message.author.id)
        if response:
            await save_message(message.channel.id, f"{bot.user}: {response}")
            await message.reply(response, mention_author=False)
            print(f"💬 [응답] {bot.user}: {response}")
        else:
            print("❌ [오류] AI 응답을 생성하지 못함")
        
            # 사용자 메시지 저장
    await save_message(message.channel.id, f"{message.author}: {message.content}")

# 사용자 메모리 업데이트 및 저장
    user_id_str = str(message.author.id)
    if user_id_str not in user_memory:
        user_memory[user_id_str] = {"name": message.author.name, "history": []}
    user_memory[user_id_str]["history"].append(message.content)
    save_user_memory()

    await bot.process_commands(message)

@bot.tree.command(name="endconversation", description="현재 채널의 대화를 종료합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def end_conversation(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    file_path = os.path.join(history_folder, f"{channel_id}.txt")
    if os.path.exists(file_path):
        os.remove(file_path)
        await interaction.response.send_message("대화가 종료되었습니다. 기존 대화 기록이 삭제되었습니다.")
    else:
        await interaction.response.send_message("대화 기록이 없습니다.")

@bot.tree.command(name="clearmemory", description="사용자 메모리를 초기화합니다.")
async def clear_memory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in user_memory:
        del user_memory[user_id]
        save_user_memory()
        await interaction.response.send_message("사용자 메모리가 초기화되었습니다.")
    else:
        await interaction.response.send_message("저장된 사용자 메모리가 없습니다.")

def generate_ai_response(user_message, user_id):
    """OpenAI GPT-4-mini를 사용하여 응답 생성"""
    user_history = user_memory.get(str(user_id), {}).get("history", [])
    conversation = [{"role": "system", "content": "You are always polite and speak in formal Korean. You are a helpful and engaging chatbot in a Discord server."}]
    for msg in user_history[-20:]:
        conversation.append({"role": "user", "content": msg})
    conversation.append({"role": "user", "content": user_message})

    try:
        response = openai.ChatCompletion.create(model="gpt-4o-mini", messages=conversation)
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ [AI 오류] {e}")
        return None

def get_summary_from_gpt(conversation_text):
    """GPT-4-mini를 사용하여 대화 내용을 요약"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant who summarizes conversations."},
                {"role": "user", "content": conversation_text}
            ]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ [AI 오류] {e}")
        return None

@bot.tree.command(name="summarize", description="대화 내용을 요약합니다.")
async def summarize(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    file_path = os.path.join(history_folder, f"{channel_id}.txt")

    if not os.path.exists(file_path):
        await interaction.response.send_message("대화 내용이 없습니다.")
        return

    with open(file_path, "r", encoding="utf-8") as file:
        conversation_text = file.read()

    summary = get_summary_from_gpt(conversation_text)
    if summary:
        await interaction.response.send_message(f"대화 내용 요약:\n{summary}")
    else:
        await interaction.response.send_message("대화 내용 요약에 실패했습니다.")

@bot.event
async def on_close():
    save_user_memory()

bot.run(DISCORD_BOT_TOKEN)
