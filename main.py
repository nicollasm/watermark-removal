# Importações de bibliotecas necessárias para a interface gráfica, processamento de vídeo, manipulação de áudio e gerenciamento de threads
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
from PIL import Image, ImageTk
import numpy as np
import threading
import moviepy.editor as mpe
import os
import time


# Classe para a janela de seleção de áreas de watermark
class SelecionarArea(tk.Toplevel):
    def __init__(self, video_path, master=None):
        super().__init__(master=master)
        self.video_path = video_path  # Caminho do vídeo para seleção de área
        self.selections = []  # Lista para armazenar seleções de áreas de watermark
        self.init_ui()

    def init_ui(self):
        self.canvas = tk.Canvas(self, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        if ret:
            self.img = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            self.canvas.create_image(0, 0, anchor="nw", image=self.img)
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.done_button = tk.Button(self, text="Concluir Seleção", command=self.concluir_selecao)
        self.done_button.pack(pady=5)
        cap.release()

    def on_button_press(self, event):
        self.x0 = event.x
        self.y0 = event.y

    def on_move_press(self, event):
        self.x1 = event.x
        self.y1 = event.y
        self.canvas.delete("rect")
        self.canvas.create_rectangle(self.x0, self.y0, self.x1, self.y1, outline='red', tag="rect")

    def on_button_release(self, event):
        self.x1 = event.x
        self.y1 = event.y
        self.selections.append((self.x0, self.y0, self.x1, self.y1))
        self.canvas.create_rectangle(self.x0, self.y0, self.x1, self.y1, outline='red')

    def concluir_selecao(self):
        self.destroy()

    def get_coords(self):
        return self.selections


# Classe principal da aplicação
class AplicacaoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Remoção de Watermark de Vídeos")
        self.geometry("800x600")
        self.videos = []
        self.areas = {}
        self.init_ui()

    def init_ui(self):
        self.btnCarregarVideos = tk.Button(self, text="Carregar Vídeos", command=self.carregar_videos)
        self.btnCarregarVideos.pack(pady=20)
        self.listaVideos = tk.Listbox(self, width=50, height=15)
        self.listaVideos.pack(pady=20)
        self.btnDefinirArea = tk.Button(self, text="Definir Área do Watermark", command=self.definir_area)
        self.btnDefinirArea.pack(pady=10)
        self.btnRemoverWatermark = tk.Button(self, text="Remover Watermark", command=self.remover_watermark)
        self.btnRemoverWatermark.pack(pady=10)
        self.progress_label = tk.Label(self, text="Progresso:")
        self.progress_label.pack(pady=5)
        self.progress_bar = ttk.Progressbar(self, length=200, mode='determinate')
        self.progress_bar.pack(pady=5)
        self.estimated_time_label = tk.Label(self, text="Tempo estimado:")
        self.estimated_time_label.pack(pady=5)

    def carregar_videos(self):
        arquivos = filedialog.askopenfilenames(title="Selecione os vídeos",
                                               filetypes=[("Arquivos de vídeo", "*.mp4 *.avi *.mov")])
        for arquivo in arquivos:
            self.videos.append(arquivo)
            self.listaVideos.insert(tk.END, arquivo.split("/")[-1])

    def definir_area(self):
        try:
            index = self.listaVideos.curselection()[0]
            video_path = self.videos[index]
            janelaSelecao = SelecionarArea(video_path, self)
            self.wait_window(janelaSelecao)
            self.areas[video_path] = janelaSelecao.get_coords()
        except IndexError:
            messagebox.showerror("Erro", "Selecione um vídeo da lista.")

    def remover_watermark(self):
        if not self.areas:
            messagebox.showerror("Erro", "Defina a área do watermark para ao menos um vídeo.")
            return
        self.total_videos = len([video for video in self.videos if video in self.areas])
        self.current_video = 0
        for video in self.videos:
            if video in self.areas:
                threading.Thread(target=self.processar_video, args=(video,)).start()

    def processar_video(self, video_path):
        start_time = time.time()
        x0, y0, x1, y1 = self.areas[video_path][0]  # Apenas a primeira área por simplicidade neste exemplo
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        temp_output = video_path.replace('.mp4', '_temp_sem_watermark.mp4')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (int(cap.get(3)), int(cap.get(4))))
        original_audio = mpe.VideoFileClip(video_path).audio
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            mascara = np.zeros(frame.shape[:2], np.uint8)
            mascara[y0:y1, x0:x1] = 255
            frame_sem_watermark = cv2.inpaint(frame, mascara, 3, cv2.INPAINT_TELEA)
            out.write(frame_sem_watermark)
            frame_count += 1
            self.update_progress(frame_count, total_frames)
        cap.release()
        out.release()
        video_sem_watermark = mpe.VideoFileClip(temp_output).subclip(0, duration)
        video_final = video_sem_watermark.set_audio(original_audio)
        video_final_path = video_path.replace('.mp4', '_final.mp4')
        video_final.write_videofile(video_final_path, codec="libx264", audio_codec="aac")
        os.remove(temp_output)
        self.current_video += 1
        if self.current_video >= self.total_videos:
            tk.messagebox.showinfo("Processamento Concluído", "Todos os vídeos foram processados.")
        end_time = time.time()
        self.update_estimated_time(end_time - start_time)

    def update_progress(self, current, total):
        self.progress_bar['value'] = (current / total) * 100
        self.update_idletasks()

    def update_estimated_time(self, time_taken):
        estimated_time_per_video = time_taken / self.total_videos
        remaining_videos = self.total_videos - self.current_video
        total_remaining_time = estimated_time_per_video * remaining_videos
        self.estimated_time_label.config(text=f"Tempo estimado restante: {total_remaining_time:.2f} segundos")


if __name__ == "__main__":
    app = AplicacaoGUI()
    app.mainloop()
