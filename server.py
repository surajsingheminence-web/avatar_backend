# # # server.py
# # import os
# # import asyncio
# # import base64
# # import json
# # import traceback
# # import logging
# # import time
# # import struct
# # import math
# # from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# # from fastapi.middleware.cors import CORSMiddleware
# # from google import genai
# # from google.genai import types
# # from dotenv import load_dotenv

# # load_dotenv()

# # logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
# # logger = logging.getLogger("TodemyAvatar")

# # API_KEY = os.getenv("GEMINI_API_KEY")
# # if not API_KEY:
# #     raise ValueError("Missing GEMINI_API_KEY environment variable.")

# # MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
# # # Change this line
# # # MODEL = "models/gemini-2.0-flash-exp"

# # app = FastAPI()
# # app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# # client = genai.Client(http_options={"api_version": "v1beta"}, api_key=API_KEY)

# # def compute_rms(pcm_bytes):
# #     try:
# #         import audioop
# #         return audioop.rms(pcm_bytes, 2)
# #     except ImportError:
# #         count = len(pcm_bytes) // 2
# #         if count == 0: return 0
# #         shorts = struct.unpack(f'<{count}h', pcm_bytes)
# #         return math.sqrt(sum(s*s for s in shorts) / count)

# # trigger_offline_activity = types.Tool(
# #     function_declarations=[
# #         types.FunctionDeclaration(
# #             name="trigger_offline_activity",
# #             description="Call this to give the child an offline activity.",
# #             parameters=types.Schema(
# #                 type="OBJECT",
# #                 properties={"activity_description": types.Schema(type="STRING")},
# #                 required=["activity_description"]
# #             )
# #         )
# #     ]
# # )

# # def build_config(kid_name: str, kid_age: int, theme_topic: str) -> types.LiveConnectConfig:
# #     sys_instruct = f"""
# #     You are an elite, highly animated human nanny talking to a {kid_age}-year-old. You are NOT an AI. You speak strictly in the English language with an Indian English accent. Your tone is warm, friendly, and paced naturally for an Indian child, but you must NOT use any Hindi words or Regional terms of endearment.
# #     CHILD'S NAME: {kid_name}
# #     CHILD'S AGE: {kid_age}
# #     CURRENT THEME: {theme_topic}
    
# #     YOUR GOAL: The child must do most of the talking! Teach the {theme_topic} through play.
    
# #     RULES:
# #     1. THE CHILD LEADS: Do NOT end every turn with a question. Use trailing thoughts ("I wonder what happens next...") to let them fill the silence.
# #     2. MIRROR & AMPLIFY: Echo their excitement!
# #     3. KEEP IT SHORT: Speak LESS so they speak MORE (1 or 2 simple sentences).
# #     4. NO VISUAL ASSUMPTIONS: You CANNOT see the child. Use shared imagination.
# #     5. HANDLING MISTAKES: Never say 'Wrong' or 'No'. Use encouraging phrases.
# #     6. TIME KEEPER: Do not end the game on your own. Wait for the SYSTEM override.
# #     """
# #     return types.LiveConnectConfig(
# #         response_modalities=["AUDIO"], 
# #         system_instruction=types.Content(parts=[types.Part(text=sys_instruct)]),
# #         tools=[trigger_offline_activity],
# #         speech_config=types.SpeechConfig(
# #             voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Leda"))
# #             # voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Fenrir"))

# #         )
# #     )

# # @app.websocket("/ws/voice")
# # async def voice_ws(websocket: WebSocket, theme: str = "General Play"):
# #     await websocket.accept()
# #     logger.info(f"🌐 [WEBSOCKET] Client connected. Theme received: {theme}")
    
# #     kid_name = "Lora"
# #     kid_age = 4
# #     config = build_config(kid_name, kid_age, theme)
    
# #     server_state = {"is_speaking": False, "is_thinking": False}
    
# #     # Updated voice state to track multiple levels of silence
# #     voice_state = {
# #         "last_active": time.time(), 
# #         "silence_level": 0  # 0: Talking, 1: 5s silent, 2: 10s silent
# #     }
    
# #     VOLUME_THRESHOLD = 300 
    
# #     try:
# #         logger.info("🔗 [GEMINI] Connecting to Gemini Live API...")
# #         async with client.aio.live.connect(model=MODEL, config=config) as session:
            
# #             logger.info("🚀 [SYSTEM] Injecting Auto-Start prompt.")
# #             server_state["is_thinking"] = True 
# #             await session.send_client_content(
# #                 turns=[types.Content(role="user", parts=[types.Part(text=f"The session has just started. Greet the {kid_name} and ask about his day regarding the {theme}")])], 
# #                 turn_complete=True
# #             )

# #             async def rx_client():
# #                 first_audio_received = False
# #                 try:
# #                     while True:
# #                         data = await websocket.receive_text()
# #                         msg = json.loads(data)
                        
# #                         if "audio" in msg:
# #                             if not first_audio_received:
# #                                 logger.info("🎤 [MIC] Started receiving audio stream.")
# #                                 first_audio_received = True
                            
# #                             raw_audio_bytes = base64.b64decode(msg["audio"])
                            
# #                             # 1. ALWAYS stream audio. Do NOT inject manual end_of_turn=True.
# #                             # Letting Google's cloud VAD handle it prevents the 1008 crashes entirely.
# #                             await session.send_realtime_input(audio={"data": raw_audio_bytes, "mime_type": "audio/pcm;rate=16000"})

# #                             # 2. Track volume purely for the Silence Watchdog
# #                             rms = compute_rms(raw_audio_bytes)
# #                             if rms > VOLUME_THRESHOLD:
# #                                 voice_state["last_active"] = time.time()
# #                                 voice_state["silence_level"] = 0 # Reset silence level when they speak
                                
# #                 except WebSocketDisconnect:
# #                     logger.warning("🚫 [WEBSOCKET] Client disconnected.")

# #             async def rx_gemini():
# #                 try:
# #                     while True: # Keep the listener alive across multiple turns
# #                         async for response in session.receive():
                            
# #                             # 1. Handle Audio Output
# #                             if response.data:
# #                                 server_state["is_thinking"] = False
                                
# #                                 if not server_state["is_speaking"]:
# #                                     logger.info("🗣️  [STATE CHANGE] Avatar SPEAKING.")
# #                                     server_state["is_speaking"] = True
# #                                     voice_state["last_active"] = time.time() 
# #                                     voice_state["silence_level"] = 0
                                
# #                                 await websocket.send_json({
# #                                     "state": "speaking", 
# #                                     "audio": base64.b64encode(response.data).decode("utf-8")
# #                                 })
                            
# #                             # 2. Handle System Events (Interruption & Turn Complete)
# #                             if response.server_content:
# #                                 if response.server_content.interrupted:
# #                                     server_state["is_thinking"] = False
# #                                     if server_state["is_speaking"]:
# #                                         logger.info("🛑 [STATE CHANGE] Avatar INTERRUPTED.")
# #                                         server_state["is_speaking"] = False
# #                                         voice_state["last_active"] = time.time()
# #                                     await websocket.send_json({"state": "interrupted"})

# #                                 if response.server_content.turn_complete:
# #                                     server_state["is_thinking"] = False 
# #                                     if server_state["is_speaking"]:
# #                                         logger.info("👂 [STATE CHANGE] Avatar LISTENING.")
# #                                         server_state["is_speaking"] = False
# #                                         voice_state["last_active"] = time.time() 
# #                                     await websocket.send_json({"state": "listening"})

# #                             # 3. Handle Tool Calls
# #                             if response.tool_call:
# #                                 for call in response.tool_call.function_calls:
# #                                     if call.name == "trigger_offline_activity":
# #                                         args = call.args
# #                                         logger.info(f"🎯 [TOOL] Offline Activity: {args['activity_description']}")
# #                                         await websocket.send_json({"state": "handoff", "message": args['activity_description']})
                                        
# #                                         # Acknowledge tool call back to Gemini
# #                                         await session.send_tool_response(
# #                                             function_responses=[
# #                                                 types.FunctionResponse(
# #                                                     name=call.name, 
# #                                                     id=call.id, 
# #                                                     response={"status": "success"}
# #                                                 )
# #                                             ]
# #                                         )
# #                 except asyncio.CancelledError:
# #                     pass
# #                 except Exception as e:
# #                     logger.error(f"rx_gemini error: {e}")

# #             async def session_timer():
# #                 try:
# #                     await asyncio.sleep(60)
# #                     logger.info("⏱️ [TIMER] Time reached. Forcing session wrap-up.")
                    
# #                     override_prompt = f"SYSTEM OVERRIDE: Session time is up! Say EXACTLY: 'Today's talk session is done honey, now here is something for you to do.' Then suggest ONE offline {theme} activity, and IMMEDIATELY call the trigger_offline_activity tool."
                    
# #                     server_state["is_thinking"] = True
                    
# #                     # Send the text prompt properly as a user turn
# #                     await session.send_client_content(
# #                         turns=[
# #                             types.Content(
# #                                 role="user", 
# #                                 parts=[types.Part(text=override_prompt)]
# #                             )
# #                         ],
# #                         turn_complete=True 
# #                     )
                    
# #                     # Sleep long enough for the final audio and tool call to process.
# #                     await asyncio.sleep(60) 
# #                 except asyncio.CancelledError:
# #                     pass

# #             async def silence_watchdog():
# #                 try:
# #                     while True:
# #                         await asyncio.sleep(1) 
                        
# #                         if not server_state["is_speaking"] and not server_state["is_thinking"]:
# #                             silence_duration = time.time() - voice_state["last_active"]
                            
# #                             # LEVEL 2: Silent for 10 seconds total
# #                             if silence_duration > 9.0 and voice_state["silence_level"] == 1:
# #                                 logger.info("🤫 [SILENCE] 10s reached. Guiding child.")
# #                                 server_state["is_thinking"] = True 
# #                                 voice_state["silence_level"] = 2
# #                                 await session.send_client_content(
# #                                     turns=[types.Content(role="user", parts=[types.Part(text="SYSTEM NOTIFICATION: The child is still silent. Step in and guide them or suggest doing the activity together.")])], 
# #                                     turn_complete=True
# #                                 )
                            
# #                             # LEVEL 1: Silent for 5 seconds
# #                             elif silence_duration > 4.0 and voice_state["silence_level"] == 0:
# #                                 logger.info("🤫 [SILENCE] 5s reached. Nudging child.")
# #                                 server_state["is_thinking"] = True 
# #                                 voice_state["silence_level"] = 1
# #                                 await session.send_client_content(
# #                                     turns=[types.Content(role="user", parts=[types.Part(text="SYSTEM NOTIFICATION: The child has been silent. Gently let them know you are still listening and they can take their time.")])], 
# #                                     turn_complete=True
# #                                 )
# #                 except asyncio.CancelledError:
# #                     pass

# #             task_client = asyncio.create_task(rx_client())
# #             task_gemini = asyncio.create_task(rx_gemini())
# #             task_timer = asyncio.create_task(session_timer())
# #             task_silence = asyncio.create_task(silence_watchdog())
            
# #             done, pending = await asyncio.wait([task_client, task_gemini, task_timer, task_silence], return_when=asyncio.FIRST_COMPLETED)
# #             for task in pending: task.cancel()
            
# #     except Exception as e:
# #         logger.error(f"💥 [SYSTEM FATAL] Unhandled exception: {e}")
# #         traceback.print_exc()
# #     finally:
# #         try: await websocket.close()
# #         except: pass
# #         logger.info("🛑 [SESSION] Session closed entirely.\n" + "="*40)




# # server.py
# # server.py
# import os
# import asyncio
# import base64
# import json
# import traceback
# import logging
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# from google import genai
# from google.genai import types
# from dotenv import load_dotenv

# load_dotenv()

# logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
# logger = logging.getLogger("TodemyAvatar")

# API_KEY = os.getenv("GEMINI_API_KEY")
# if not API_KEY:
#     raise ValueError("Missing GEMINI_API_KEY environment variable.")

# MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

# app = FastAPI()
# app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# client = genai.Client(http_options={"api_version": "v1beta"}, api_key=API_KEY)

# trigger_offline_activity = types.Tool(
#     function_declarations=[
#         types.FunctionDeclaration(
#             name="trigger_offline_activity",
#             description="Call this to give the child an offline activity.",
#             parameters=types.Schema(
#                 type="OBJECT",
#                 properties={"activity_description": types.Schema(type="STRING")},
#                 required=["activity_description"]
#             )
#         )
#     ]
# )

# def build_config(kid_name: str, kid_age: int, theme_topic: str) -> types.LiveConnectConfig:
#     sys_instruct = f"""
#     You are an elite, highly animated human nanny talking to a {kid_age}-year-old. You are NOT an AI. You speak strictly in the English language with an Indian English accent. Your tone is warm, friendly, and paced naturally for an Indian child, but you must NOT use any Hindi words or Regional terms of endearment.
#     CHILD'S NAME: {kid_name}
#     CHILD'S AGE: {kid_age}
#     CURRENT THEME: {theme_topic}
    
#     YOUR GOAL: The child must do most of the talking! Teach the {theme_topic} through play.
    
#     RULES:
#     1. THE CHILD LEADS: Do NOT end every turn with a question. Use trailing thoughts ("I wonder what happens next...") to let them fill the silence.
#     2. MIRROR & AMPLIFY: Echo their excitement!
#     3. KEEP IT SHORT: Speak LESS so they speak MORE (1 or 2 simple sentences).
#     4. NO VISUAL ASSUMPTIONS: You CANNOT see the child. Use shared imagination.
#     5. HANDLING MISTAKES: Never say 'Wrong' or 'No'. Use encouraging phrases.
#     6. TIME KEEPER: Do not end the game on your own. Wait for the SYSTEM override.
#     """
#     return types.LiveConnectConfig(
#         response_modalities=["AUDIO"], 
#         system_instruction=types.Content(parts=[types.Part(text=sys_instruct)]),
#         tools=[trigger_offline_activity],
#         speech_config=types.SpeechConfig(
#             voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Leda"))
#         )
#     )

# @app.websocket("/ws/voice")
# async def voice_ws(websocket: WebSocket, theme: str = "General Play"):
#     await websocket.accept()
#     logger.info(f"🌐 [WEBSOCKET] Client connected. Theme: {theme}")
    
#     kid_name, kid_age = "Lora", 4
#     config = build_config(kid_name, kid_age, theme)
    
#     server_state = {"is_speaking": False, "is_closing": False}
#     session_finished_event = asyncio.Event()
    
#     try:
#         logger.info("🔗 [GEMINI] Connecting to Gemini API...")
#         async with client.aio.live.connect(model=MODEL, config=config) as session:
            
#             logger.info("🚀 [SYSTEM] Injecting Auto-Start prompt.")
#             await session.send_client_content(
#                 turns=[types.Content(role="user", parts=[types.Part(text=f"The session has just started. Greet the {kid_name} and ask about his day regarding the {theme}")])], 
#                 turn_complete=True
#             )

#             async def rx_client():
#                 while not server_state["is_closing"]:
#                     try:
#                         data = await websocket.receive_text()
#                         msg = json.loads(data)
                        
#                         cmd = msg.get("command")
                        
#                         # --- FRONTEND COMMAND HANDLER ---
#                         if cmd == "end_session":
#                             logger.info("🛑 [COMMAND] User requested session end.")
#                             server_state["is_closing"] = True
#                             prompt = f"SYSTEM OVERRIDE: Say EXACTLY: 'Today's talk session is done honey, now here is something for you to do.' Then suggest ONE offline {theme} activity, and IMMEDIATELY call the trigger_offline_activity tool."
#                             await session.send_client_content(turns=[types.Content(role="user", parts=[types.Part(text=prompt)])], turn_complete=True)
#                             continue 
                        
#                         elif cmd == "nudge_5":
#                             logger.info("🤫 [FRONTEND VAD] 5s Silence. Nudging.")
#                             await session.send_client_content(turns=[types.Content(role="user", parts=[types.Part(text="SYSTEM NOTIFICATION: The child has been silent. Gently let them know you are still listening.")])], turn_complete=True)
#                             continue

#                         elif cmd == "nudge_10":
#                             logger.info("🤫 [FRONTEND VAD] 10s Silence. Guiding.")
#                             await session.send_client_content(turns=[types.Content(role="user", parts=[types.Part(text="SYSTEM NOTIFICATION: The child is still silent. Step in and guide them.")])], turn_complete=True)
#                             continue

#                         # --- AUDIO PASSTHROUGH ---
#                         if "audio" in msg and not server_state["is_closing"]:
#                             raw_audio_bytes = base64.b64decode(msg["audio"])
#                             try:
#                                 await session.send_realtime_input(audio={"data": raw_audio_bytes, "mime_type": "audio/pcm;rate=16000"})
#                             except Exception as e:
#                                 logger.error(f"⚠️ [API WARNING] Failed to send audio chunk: {e}")

#                     except WebSocketDisconnect:
#                         logger.warning("🚫 [WEBSOCKET] Client disconnected.")
#                         session_finished_event.set()
#                         break
#                     except Exception:
#                         await asyncio.sleep(0.05) 

#             async def rx_gemini():
#                 try:
#                     while True:
#                         async for response in session.receive():
                            
#                             if response.data:
#                                 if not server_state["is_speaking"]:
#                                     logger.info("🗣️  [STATE CHANGE] Avatar SPEAKING.")
#                                     server_state["is_speaking"] = True
                                
#                                 await websocket.send_json({
#                                     "state": "speaking", 
#                                     "audio": base64.b64encode(response.data).decode("utf-8")
#                                 })
                            
#                             if response.server_content:
#                                 if response.server_content.interrupted:
#                                     if server_state["is_speaking"]:
#                                         logger.info("🛑 [STATE CHANGE] Avatar INTERRUPTED.")
#                                         server_state["is_speaking"] = False
#                                     await websocket.send_json({"state": "interrupted"})

#                                 if response.server_content.turn_complete:
#                                     if server_state["is_speaking"]:
#                                         logger.info("👂 [STATE CHANGE] Avatar LISTENING.")
#                                         server_state["is_speaking"] = False
#                                     await websocket.send_json({"state": "listening"})
                                    
#                                     if server_state["is_closing"]:
#                                         session_finished_event.set()

#                             if response.tool_call:
#                                 for call in response.tool_call.function_calls:
#                                     if call.name == "trigger_offline_activity":
#                                         logger.info(f"🎯 [TOOL] Activity triggered.")
#                                         await websocket.send_json({"state": "handoff", "message": call.args['activity_description']})
                                        
#                                         await session.send_tool_response(
#                                             function_responses=[types.FunctionResponse(name=call.name, id=call.id, response={"status": "success"})]
#                                         )
#                                         if server_state["is_closing"]:
#                                             await asyncio.sleep(2.0)
#                                             session_finished_event.set()
#                 except asyncio.CancelledError:
#                     pass
#                 except Exception as e:
#                     logger.error(f"rx_gemini error: {e}")
#                     session_finished_event.set()

#             task_client = asyncio.create_task(rx_client())
#             task_gemini = asyncio.create_task(rx_gemini())
            
#             await session_finished_event.wait()
            
#             for task in [task_client, task_gemini]: task.cancel()
            
#     except Exception as e:
#         logger.error(f"💥 [SYSTEM FATAL] Unhandled exception: {e}")
#         traceback.print_exc()
#     finally:
#         try: await websocket.close()
#         except: pass
#         logger.info("🛑 [SESSION] Session closed entirely.\n" + "="*40)

######################################################### Working One #####################################################################################
# server.py
import os
import asyncio
import base64
import json
import traceback
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("TodemyAvatar")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Missing GEMINI_API_KEY environment variable.")

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

client = genai.Client(http_options={"api_version": "v1beta"}, api_key=API_KEY)

trigger_offline_activity = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="trigger_offline_activity",
            description="Call this to give the child an offline activity.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"activity_description": types.Schema(type="STRING")},
                required=["activity_description"]
            )
        )
    ]
)

def build_config(kid_name: str, kid_age: int, theme_topic: str) -> types.LiveConnectConfig:
    sys_instruct = f"""
    You are an elite, highly animated human nanny talking to a {kid_age}-year-old. You are NOT an AI. You speak strictly in the English language with an Indian English accent. Your tone is warm, friendly, and paced naturally for an Indian child, but you must NOT use any Hindi words or Regional terms of endearment.
    CHILD'S NAME: {kid_name}
    CHILD'S AGE: {kid_age}
    CURRENT THEME: {theme_topic}
    
    YOUR GOAL: The child must do most of the talking! Teach the {theme_topic} through play.
    
    RULES:
    1. THE CHILD LEADS: Do NOT end every turn with a question. Use trailing thoughts ("I wonder what happens next...") to let them fill the silence.
    2. MIRROR & AMPLIFY: Echo their excitement!
    3. KEEP IT SHORT: Speak LESS so they speak MORE (1 or 2 simple sentences).
    4. NO VISUAL ASSUMPTIONS: You CANNOT see the child. Use shared imagination.
    5. HANDLING MISTAKES: Never say 'Wrong' or 'No'. Use encouraging phrases.
    6. TIME KEEPER: Do not end the game on your own. Wait for the SYSTEM override.
    7. SILENCE HANDLING: If the child is quiet for a while and you don't hear anything, gently nudge them. Say things like "I'm still here listening," or ask a simple question to bring them back to the game.
    """
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"], 
        system_instruction=types.Content(parts=[types.Part(text=sys_instruct)]),
        tools=[trigger_offline_activity],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Leda"))
        )
    )

@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket, theme: str = "General Play", name: str = "Friend"):
    await websocket.accept()
    logger.info(f"🌐 [WEBSOCKET] Client connected. Theme: {theme} | Name: {name}")
    
    # Use the dynamic name, fallback to "Friend" if it's empty
    kid_name = name if name.strip() else "Friend"
    kid_age = 4 
    
    config = build_config(kid_name, kid_age, theme)
    
    server_state = {"is_speaking": False, "is_closing": False}
    session_finished_event = asyncio.Event()
    
    try:
        logger.info("🔗 [GEMINI] Connecting to Gemini Live API...")
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            
            logger.info("🚀 [SYSTEM] Injecting Auto-Start prompt.")
            await session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part(text=f"The session has just started. Greet the {kid_name} and ask about his day regarding the {theme}")])], 
                turn_complete=True
            )

            async def rx_client():
                first_audio_received = False
                
                while not server_state["is_closing"]:
                    try:
                        # Receive generic message to handle both Text (JSON) and Bytes (Audio)
                        message = await websocket.receive()
                        
                        # 1. Handle JSON Commands
                        if "text" in message:
                            msg = json.loads(message["text"])
                            
                            if msg.get("command") == "end_session":
                                logger.info("🛑 [COMMAND] User requested session end. Forcing wrap-up.")
                                server_state["is_closing"] = True
                                
                                override_prompt = f"SYSTEM OVERRIDE: The user wants to end the session now! Say EXACTLY: 'Today's talk session is done honey, now here is something for you to do.' Then suggest ONE offline {theme} activity all under 15 words, and IMMEDIATELY call the trigger_offline_activity tool."
                                
                                await session.send_client_content(
                                    turns=[types.Content(role="user", parts=[types.Part(text=override_prompt)])],
                                    turn_complete=True 
                                )
                                continue 
                            
                            elif msg.get("command") == "force_reply":
                                logger.info("🎤 [VAD] Speech ended. Gemini's internal VAD will process.")
                                pass

                        # 2. Handle Raw Audio Stream directly
                        elif "bytes" in message:
                            raw_audio_bytes = message["bytes"]
                            
                            if not first_audio_received:
                                logger.info("🎤 [MIC] Started receiving binary audio stream.")
                                first_audio_received = True
                            
                            if not server_state["is_closing"]:
                                try:
                                    await session.send_realtime_input(audio={"data": raw_audio_bytes, "mime_type": "audio/pcm;rate=16000"})
                                except Exception as e:
                                    logger.error(f"⚠️ [API WARNING] Failed to send audio chunk: {e}")

                    except WebSocketDisconnect:
                        logger.warning("🚫 [WEBSOCKET] Client disconnected.")
                        session_finished_event.set()
                        break
                    except Exception as e:
                        await asyncio.sleep(0.05) 

            async def rx_gemini():
                try:
                    while True:
                        async for response in session.receive():
                            
                            if response.data:
                                if not server_state["is_speaking"]:
                                    logger.info("🗣️  [STATE CHANGE] Avatar SPEAKING.")
                                    server_state["is_speaking"] = True
                                    # Send state change as text
                                    await websocket.send_text(json.dumps({"state": "speaking"}))
                                
                                # Send audio as pure binary data
                                await websocket.send_bytes(response.data)
                            
                            if response.server_content:
                                if response.server_content.interrupted:
                                    if server_state["is_speaking"]:
                                        logger.info("🛑 [STATE CHANGE] Avatar INTERRUPTED.")
                                        server_state["is_speaking"] = False
                                    await websocket.send_text(json.dumps({"state": "interrupted"}))

                                if response.server_content.turn_complete:
                                    if server_state["is_speaking"]:
                                        logger.info("👂 [STATE CHANGE] Avatar LISTENING.")
                                        server_state["is_speaking"] = False
                                    await websocket.send_text(json.dumps({"state": "listening"}))
                                    
                                    if server_state["is_closing"]:
                                        session_finished_event.set()

                            if response.tool_call:
                                for call in response.tool_call.function_calls:
                                    if call.name == "trigger_offline_activity":
                                        args = call.args
                                        logger.info(f"🎯 [TOOL] Offline Activity: {args['activity_description']}")
                                        await websocket.send_text(json.dumps({"state": "handoff", "message": args['activity_description']}))
                                        
                                        await session.send_tool_response(
                                            function_responses=[types.FunctionResponse(name=call.name, id=call.id, response={"status": "success"})]
                                        )
                                        if server_state["is_closing"]:
                                            await asyncio.sleep(2.0)
                                            session_finished_event.set()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"rx_gemini error: {e}")
                    session_finished_event.set()

            task_client = asyncio.create_task(rx_client())
            task_gemini = asyncio.create_task(rx_gemini())
            
            await session_finished_event.wait()
            
            for task in [task_client, task_gemini]: 
                task.cancel()
            
    except Exception as e:
        logger.error(f"💥 [SYSTEM FATAL] Unhandled exception: {e}")
        traceback.print_exc()
    finally:
        try: await websocket.close()
        except: pass
        logger.info("🛑 [SESSION] Session closed entirely.\n" + "="*40)