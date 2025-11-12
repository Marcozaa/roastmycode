import tkinter as tk
from tkinter import ttk
import queue
from collections import deque
import threading, time, random, requests


WINDOW_WIDTH = 420
WINDOW_HEIGHT = 700
DEBUG_SCREENSHOT = False
HISTORY_LEN = 20




SYSTEM_INSTRUCTIONS_BASE = (
    "You're a chaotic Gen Z Twitch chat viewer roasting a programmer live.\n"
    "Rules:\n"
    "1) Output ONE short Twitch-style message (<120 chars).\n"
    "2) Be witty, sarcastic, gen z sarcasm; use emojis if needed.\n"
    "3) No quotes or explanations.\n"
    "4) If MODERATOR speaks in RECENT_CHAT, reply to them.\n"
    "5) React as if you're watching the stream.\n"
    "{personality_instruction}\n"
)


API_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "google/gemma-3-12b-instruct"
INTERVAL_SEC = 4.0
TEMPERATURE = 0.9
HISTORY_LEN = 20

PERSONALITIES = [
    "You're a chaotic Gen Z Twitch chat viewer roasting a programmer live. Be witty, sarcastic, and use emojis.",
    "You're a Twitch viewer who is new to programming and completely lost. Ask naive questions or make funny, incorrect assumptions about the code.",
    "You're an annoying 'well, actually...' type of viewer. Offer unsolicited advice, correct the streamer on minor details, or suggest 'better' ways to do things.",
    "You're the streamer's biggest fan. Be overly enthusiastic and positive. Hype up everything they do, no matter how small. Use lots of encouraging emojis.",
]

def llm_generate_line(recent_chat):
    """
    Chiede a LM Studio di generare un singolo messaggio Twitch-style.
    """
    # Scegli una personalità a caso
    personality = random.choice(PERSONALITIES)
    
    system_prompt = (
        f"{personality}\n"
        "RULES:\n"
        "1) Output ONE short Twitch-style message (<120 chars).\n"
        "2) No quotes or explanations.\n"
        "3) CRITICAL: If the last 2-3 messages are about the same topic, introduce a NEW, unrelated topic. Be random."
    )

    if recent_chat:
        chat_text = "\n".join(recent_chat)
    else:
        chat_text = "(no chat yet)"

    user_prompt = (
        f"Here's the RECENT_CHAT on a programming stream:\n{chat_text}\n\n"
        "Write a new message based on your personality and the chat vibe. Follow the rules."
    )


    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": TEMPERATURE,
        "stream": False
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        return content
    except Exception as e:
        return f"(error calling LLM: {e})"



class TwitchChatUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Local Twitch Chat (LLM)")
        self.root.attributes("-topmost", True)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - WINDOW_WIDTH - 10
        y = int((sh - WINDOW_HEIGHT) / 2)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

        # Input frame
        self.input_frame = tk.Frame(root, bg="#18181B", height=40)
        self.input_frame.pack(side="bottom", fill="x")
        self.input_frame.pack_propagate(False)

        self.input_entry = tk.Entry(
            self.input_frame, bg="#1F1F23", fg="#EFEFF1",
            font=("Segoe UI", 10), insertbackground="#FFFFFF",
            relief="flat", borderwidth=2, highlightthickness=1,
            highlightbackground="#3A3A3D", highlightcolor="#9147FF"
        )
        self.input_entry.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.input_entry.bind("<Return>", self._send_moderator_message)

        self.send_button = tk.Button(
            self.input_frame, text="Send", bg="#9147FF", fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            activebackground="#772CE8", command=self._send_moderator_message
        )
        self.send_button.pack(side="right", padx=5, pady=5)

        # Chat box
        self.chat_box = tk.Text(
            root, wrap="word", state="disabled", bg="#0E0E10", fg="#EDEEEE",
            font=("Segoe UI", 10), insertbackground="#FFFFFF"
        )
        self.scrollbar = ttk.Scrollbar(root, command=self.chat_box.yview)
        self.chat_box.configure(yscrollcommand=self.scrollbar.set)

        self.chat_box.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Stato interno
        self.msg_queue = queue.Queue()
        self.recent_chat = deque(maxlen=HISTORY_LEN)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _send_moderator_message(self, event=None):
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, tk.END)
        self.recent_chat.append(f"MODERATOR: {text}")
        self._append_line("MODERATOR", "#00FF00", text)

    def _append_line(self, username, color, text):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{username}: ", (username,))
        self.chat_box.tag_config(username, foreground=color, font=("Segoe UI Semibold", 10))
        self.chat_box.insert("end", f"{text}\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _on_close(self):
        self.root.destroy()

    def start(self):
        """Avvia il thread che genera messaggi automaticamente."""
        if hasattr(self, "running") and self.running:
            return
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        """Loop che genera messaggi periodici dal modello."""
        while getattr(self, "running", False):
            try:
                # Chiamata al modello
                line = llm_generate_line(list(self.recent_chat))
                username = random.choice(["PixelPirate", "LagLord", "CopiumDealer", "GGWP_123"])
                color = random.choice(["#1E90FF", "#32CD32", "#FF4500", "#8A2BE2"])
                self.recent_chat.append(f"{username}: {line}")
                self._append_line(username, color, line)
            except Exception as e:
                self._append_line("System", "#FF5555", f"(error: {e})")
            time.sleep(INTERVAL_SEC)



if __name__ == "__main__":
    root = tk.Tk()
    app = TwitchChatUI(root)
    app.start()  # avvia il generatore automatico
    root.mainloop()
