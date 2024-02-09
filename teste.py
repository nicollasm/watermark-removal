# Importa as bibliotecas necessárias
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
from PIL import Image, ImageTk
import numpy as np
import threading
import moviepy.editor as mpe
import os
import time
from queue import Queue


# Classe para seleção de área no vídeo
class SelecionarArea(tk.Toplevel):
    # Inicializa a janela de seleção de área
    def __init__(self, video_path, master=None):
        super().__init__(master=master)
        self.video_path = video_path
        self.selections = []
        self.undo_stack = []
        self.init_ui()

    # Configura a interface do usuário
    def init_ui(self):
        self.canvas = tk.Canvas(self, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = Image.fromarray(frame)
            self.img = ImageTk.PhotoImage(image=self.photo)
            self.canvas.create_image(0, 0, anchor="nw", image=self.img)
            self.update()  # Atualiza a janela
            self.geometry(f"{self.img.width()}x{self.img.height()}")  # Ajusta o tamanho da janela
        cap.release()
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.done_button = tk.Button(self, text="Concluir Seleção", command=self.concluir_selecao)
        self.done_button.pack(pady=5)
        self.undo_button = tk.Button(self, text="Desfazer", command=self.undo_selection)
        self.undo_button.pack(pady=5)

    # Evento de pressionamento do botão do mouse
    def on_button_press(self, event):
        self.x0 = event.x
        self.y0 = event.y

    # Evento de movimento do mouse com botão pressionado
    def on_move_press(self, event):
        self.x1 = event.x
        self.y1 = event.y
        self.canvas.delete("rect")
        self.canvas.create_rectangle(self.x0, self.y0, self.x1, self.y1, outline='red', tag="rect")

    # Evento de liberação do botão do mouse
    def on_button_release(self, event):
        selection = (self.x0, self.y0, self.x1, self.y1)
        self.selections.append(selection)
        self.undo_stack.append(selection)
        self.canvas.create_rectangle(self.x0, self.y0, self.x1, self.y1, outline='red')

    # Desfaz a última seleção feita
    def undo_selection(self):
        if self.undo_stack:
            last_selection = self.undo_stack.pop()
            self.selections.remove(last_selection)
            self.canvas.delete("rect")
            for selection in self.selections:
                self.canvas.create_rectangle(*selection, outline='red')

    # Conclui a seleção de área
    def concluir_selecao(self):
        self.destroy()

    # Retorna as coordenadas das áreas selecionadas
    def get_coords(self):
        return self.selections


# Classe principal da aplicação GUI
class AplicacaoGUI(tk.Tk):
    # Inicializa a aplicação GUI
    def __init__(self):
        super().__init__()
        self.title("Remoção de Watermark de Vídeos")
        self.geometry("800x600")
        self.videos = []
        self.areas = {}
        self.queue = Queue()
        self.init_ui()

    # Configura a interface do usuário
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

    # Carrega vídeos para processamento
    def carregar_videos(self):
        arquivos = filedialog.askopenfilenames(title="Selecione os vídeos",
                                               filetypes=[("Arquivos de vídeo", "*.mp4 *.avi *.mov")])
        for arquivo in arquivos:
            if arquivo.lower().endswith(('.mp4', '.avi', '.mov')):
                self.videos.append(arquivo)
                self.listaVideos.insert(tk.END, arquivo.split("/")[-1])
            else:
                messagebox.showwarning("Arquivo não suportado", "Por favor, selecione um arquivo de vídeo válido.")

    # Define a área do watermark para o vídeo selecionado
    def definir_area(self):
        try:
            index = self.listaVideos.curselection()[0]
            video_path = self.videos[index]
            janelaSelecao = SelecionarArea(video_path, self)
            self.wait_window(janelaSelecao)
            self.areas[video_path] = janelaSelecao.get_coords()
        except IndexError:
            messagebox.showerror("Erro", "Selecione um vídeo da lista.")

    # Inicia o processo de remoção do watermark
    def remover_watermark(self):
        if not self.areas:
            messagebox.showerror("Erro", "Defina a área do watermark para ao menos um vídeo.")
            return
        self.total_videos = len([video for video in self.videos if video in self.areas])
        self.current_video = 0
        for video in self.videos:
            if video in self.areas:
                thread = threading.Thread(target=self.processar_video, args=(video,))
                thread.start()

    # Processa o vídeo para remover o watermark
    def processar_video(self, video_path):
        start_time = time.time()
        # Configuração inicial para processamento de vídeo
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
            for x0, y0, x1, y1 in self.areas[video_path]:
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

    # Atualiza o progresso na barra de progresso
    def update_progress(self, current, total):
        self.progress_bar['value'] = (current / total) * 100
        self.update_idletasks()

    # Atualiza o tempo estimado restante
    def update_estimated_time(self, time_taken):
        estimated_time_per_video = time_taken / self.total_videos
        remaining_videos = self.total_videos - self.current_video
        total_remaining_time = estimated_time_per_video * remaining_videos
        self.estimated_time_label.config(text=f"Tempo estimado restante: {total_remaining_time:.2f} segundos")


# Inicia a aplicação
if __name__ == "__main__":
    app = AplicacaoGUI()
    app.mainloop()
