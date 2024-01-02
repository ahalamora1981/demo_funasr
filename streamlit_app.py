import streamlit as st
import os
import wave
import time
import asyncio
import websockets
from pydub import AudioSegment
from st_audiorec import st_audiorec


# 设置服务器地址和端口
IP_ADDRESS = '47.117.37.29'
# IP_ADDRESS = 'localhost'
PORT = 10001

# 设置参数
SAMPLE_WIDTH = 2
SAMPLE_RATE = 16000
CHUNK_SECONDS = 0.6  # 单个Chunk的秒数
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_SECONDS) * SAMPLE_WIDTH

# 指定输出wav文件的相关参数
CHANNELS = 1                # 单声道，可以根据实际情况调整
FRAMES = 1024               # 每帧的样本数，可以根据实际情况调整
# CHANNELS = 1
# FORMAT_TYPE = pyaudio.paInt16
TEMP_DIR = 'temp'

def seconds_to_hms(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    hours = str(int(hours)) if len(str(int(hours))) != 1 else f"0{str(int(hours))}"
    minutes = str(int(minutes)) if len(str(int(minutes))) != 1 else f"0{str(int(minutes))}"
    seconds = str(round(seconds, 2)) if seconds >= 10 else f"0{round(seconds, 2)}"
    seconds = seconds if len(seconds) == 5 else f"{seconds}0"
    return hours, minutes, seconds

def save_uploaded_file(uploaded_file):
    file_path = os.path.join(TEMP_DIR, uploaded_file.name)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path

def load_file_and_start_main(saved_file_path, format, frame_rate):
    # 更新采样率
    audio_object = AudioSegment.from_file(
        saved_file_path, 
        format=format, 
        sample_width=SAMPLE_WIDTH, 
        frame_rate=frame_rate, 
        channels=1
        )

    if format == "pcm":
        audio_data = audio_object.set_frame_rate(SAMPLE_RATE).raw_data
    elif format == "wav":
        mono_channels = audio_object.split_to_mono()
        # 选择左声道
        selected_channel = mono_channels[0]
        # 转换采样率
        audio_data = selected_channel.set_frame_rate(SAMPLE_RATE).raw_data
    else:
        print("文件格式错误")
            
    asyncio.run(main(audio_data))

async def main(audio_data):
    global uploaded_file
    
    # 发送数据到WebSocket服务器
    websocket_uri = f"ws://{IP_ADDRESS}:{str(PORT)}"
    
    async with websockets.connect(websocket_uri) as websocket:
        try:
            text_all = str()
            text_realtime = str()
            text_realtime_all = str()

            for i in range(0, len(audio_data), CHUNK_SIZE):
                current_time = time.time()
                hours, minutes, seconds = seconds_to_hms((i/CHUNK_SIZE) * CHUNK_SECONDS)
                
                chunk = audio_data[i : i+CHUNK_SIZE]
                # print(f"Chunk Length: {len(chunk)}")
                
                await websocket.send(chunk)
                response = await websocket.recv()
                response_text = response.decode() if response.decode() != "<|None|>" else ""
                
                text_all += response_text
                text_realtime = f"[{minutes}:{seconds}] - {response_text}"
                st.write(text_realtime)
                
                text_realtime_all += text_realtime + "\n"

                end_time = time.time()
                elapsed_time = end_time - current_time

                # 计算需要等待的时间
                if not fast:
                    wait_time = max(0, CHUNK_SECONDS - elapsed_time)
                else:
                    wait_time = 0

                # 等待一段时间，以保证总时长为0.6秒
                time.sleep(wait_time)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await websocket.send("<|Transcription|>".encode())
            transcription = await websocket.recv()
            print("【实时转写(All)】", text_all)
            
            # text_file_url = os.path.join(TEMP_DIR, "transcription.txt")
            # with open(text_file_url, "w") as f:
            #     f.write("【实时转写内容】" + text_realtime_all + "\n【全文转写内容】" + text_all)
            
            output_text = f"【实时转写】\n{text_realtime_all}\n【实时转写(All)】\n{text_all}\n\n【全文转写】\n{transcription.decode()}"
            
            download_btn = st.download_button(
                label="下载转写结果",
                data=output_text,
                file_name='output.txt',
                mime='text/csv',
            )
            
            if download_btn:
                st.stop()

if __name__ == "__main__":
    st.header("录音转写Demo(实时&全文)")
    
    tab_1, tab_2 = st.tabs(["录音文件转写", "麦克风录音转写"])
    
    with tab_1:
        st.subheader("录音文件转写 Demo :phone::arrow_right::page_facing_up:")
        st.write("##### 支持音频格式 :")
        st.write("**PCM** | 8K 采样率 | 16位 | 单声道")
        st.write("**WAV** | 不限采样率 | 16位 | 单声道 | 双声道的左声道")  

        fast = st.toggle('快速模式', value=True)    
        uploaded_file = st.file_uploader("上传音频文件", type=["wav", "pcm"])

        if uploaded_file is not None:
            # st.audio(uploaded_file.read(), format="audio/pcm", start_time=0)
            st.success("音频文件上传成功！")
            saved_file_path = save_uploaded_file(uploaded_file)

            if '.pcm' in uploaded_file.name:
                format = 'pcm'
                frame_rate = 8000
            elif '.wav' in uploaded_file.name:
                format = 'wav'
                # 打开WAV文件
                with wave.open(saved_file_path, 'rb') as audio_file:
                    # 获取采样率
                    frame_rate = audio_file.getframerate()
            else:
                print("文件格式错误")
            
            if st.button("开始实时转写"):
                load_file_and_start_main(saved_file_path, format, frame_rate)
        
    with tab_2:
        st.subheader("麦克风录音转写 Demo :studio_microphone::arrow_right::page_facing_up:")
        frame_rate = 96000
        wav_audio_data = st_audiorec()

        if wav_audio_data is not None:
            if st.button("开始转写"):
                # 创建Wave_write对象
                with wave.open('temp/temp.wav', 'w') as wave_file:
                    # 设置wav文件的参数
                    wave_file.setsampwidth(SAMPLE_WIDTH)
                    wave_file.setnchannels(CHANNELS)
                    wave_file.setframerate(frame_rate)
                    wave_file.setnframes(FRAMES)

                    # 写入二进制音频数据
                    wave_file.writeframes(wav_audio_data)
                    
                    
                load_file_and_start_main(
                    saved_file_path='temp/temp.wav',
                    format='wav',
                    frame_rate=frame_rate
                    )
