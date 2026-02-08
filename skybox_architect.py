import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from tkinter import filedialog
from PIL import Image, ImageOps
import os
import numpy as np
import threading
import zipfile
import io

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ImageProcessor:    
    @staticmethod
    def get_cubemap_coordinates(face, size, yaw_deg, pitch_deg):
        grid = np.indices((size, size), dtype=np.float32)
        y, x = grid[0], grid[1]
        
        tx = 2.0 * (x + 0.5) / size - 1.0
        ty = 2.0 * (y + 0.5) / size - 1.0
        
        if face == "front":  vx, vy, vz =  1.0,  tx, -ty
        elif face == "back": vx, vy, vz = -1.0, -tx, -ty
        elif face == "left":  vx, vy, vz = -tx,  1.0, -ty
        elif face == "right": vx, vy, vz =  tx, -1.0, -ty
        elif face == "top":    vx, vy, vz = -ty,  tx,  1.0
        elif face == "bottom": vx, vy, vz =  ty,  tx, -1.0
        else: return None

        yaw = np.radians(yaw_deg)
        pitch = np.radians(pitch_deg)

        cp, sp = np.cos(pitch), np.sin(pitch)
        nx = vx * cp + vz * sp
        ny = vy
        nz = -vx * sp + vz * cp

        cy, sy = np.cos(yaw), np.sin(yaw)
        rx = nx * cy - ny * sy
        ry = nx * sy + ny * cy
        rz = nz
        
        return rx, ry, rz

    @staticmethod
    def remap_face(img_array, face, size, yaw, pitch):
        h_pan, w_pan = img_array.shape[:2]
        
        rx, ry, rz = ImageProcessor.get_cubemap_coordinates(face, size, yaw, pitch)
        
        mag = np.sqrt(rx**2 + ry**2 + rz**2)
        phi = np.arctan2(ry, rx)
        theta = np.arcsin(rz / mag)
        
        ratio_scale = (w_pan / h_pan) / 2.0
        
        u = (phi + np.pi) / (2 * np.pi) * (w_pan - 1)
        v = (np.pi/2 - theta * (1/ratio_scale)) / np.pi * (h_pan - 1)
        
        u = np.clip(u, 0, w_pan - 1.001)
        v = np.clip(v, 0, h_pan - 1.001)
        
        u0 = np.floor(u).astype(int)
        v0 = np.floor(v).astype(int)
        
        u1 = np.clip(u0 + 1, 0, w_pan - 1)
        v1 = np.clip(v0 + 1, 0, h_pan - 1)
        
        du = (u - u0)[..., None]
        dv = (v - v0)[..., None]
        
        p00 = img_array[v0, u0]
        p01 = img_array[v0, u1]
        p10 = img_array[v1, u0]
        p11 = img_array[v1, u1]
        
        return (p00*(1-du)*(1-dv) + p01*du*(1-dv) + p10*(1-du)*dv + p11*du*dv).astype(np.uint8)

class SkyboxSmartFix(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Skybox Architect")
        self.geometry("1280x920")
        
        self.panorama_array = None 
        self.original_image = None 
        self.face_images = {} 
        self.preview_cache = {} 
        
        self.is_processing = False
        self.face_rotations = {"top": 270, "bottom": 90}
        
        self.prefix_var = ctk.StringVar(value="sky")
        self.pk3_name_var = ctk.StringVar(value="my_skybox")
        self.size_var = ctk.StringVar(value="1024")
        self.format_var = ctk.StringVar(value="JPG")
        self.quality_var = ctk.IntVar(value=100)
        self.yaw_offset = ctk.DoubleVar(value=0)
        self.pitch_offset = ctk.DoubleVar(value=0)
        self.flip_up = ctk.BooleanVar(value=True)
        self.status_var = ctk.StringVar(value="Ready")
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(13, weight=1) 

        ctk.CTkLabel(self.sidebar, text="SKYBOX ARCHITECT", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(self.sidebar, text="Equirectangular → Cubemap", font=ctk.CTkFont(size=12)).pack(pady=(0, 20))

        self.btn_import = ctk.CTkButton(self.sidebar, text="Import Panorama", command=self.load_image, height=40)
        self.btn_import.pack(padx=20, pady=10, fill="x")

        self.create_separator(self.sidebar, "Settings")
        
        self.create_labeled_entry(self.sidebar, "Prefix:", self.prefix_var)
        self.create_labeled_entry(self.sidebar, "PK3 Name:", self.pk3_name_var)
        
        ctk.CTkLabel(self.sidebar, text="Output Size:", anchor="w").pack(padx=20, pady=(10, 0), fill="x")
        self.size_menu = ctk.CTkOptionMenu(self.sidebar, values=["512", "1024", "2048", "4096"], variable=self.size_var, command=self.trigger_high_res)
        self.size_menu.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(self.sidebar, text="File Format:", anchor="w").pack(padx=20, pady=(10, 0), fill="x")
        self.format_menu = ctk.CTkOptionMenu(self.sidebar, values=["JPG", "TGA"], variable=self.format_var, command=self.toggle_quality_state)
        self.format_menu.pack(padx=20, pady=5, fill="x")

        self.quality_label = ctk.CTkLabel(self.sidebar, text="JPG Quality: 100", anchor="w")
        self.quality_label.pack(padx=20, pady=(10, 0), fill="x")
        self.quality_slider = ctk.CTkSlider(self.sidebar, from_=1, to=100, number_of_steps=99, variable=self.quality_var, command=self.update_quality_label)
        self.quality_slider.pack(padx=20, pady=5, fill="x")

        self.create_separator(self.sidebar, "Orientation")
        
        ctk.CTkLabel(self.sidebar, text="Yaw (Horizontal)", anchor="w").pack(padx=20, pady=(5,0), fill="x")
        self.yaw_slider = ctk.CTkSlider(self.sidebar, from_=-180, to=180, variable=self.yaw_offset, command=self.on_slider_drag)
        self.yaw_slider.bind("<ButtonRelease-1>", self.on_slider_release)
        self.yaw_slider.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(self.sidebar, text="Pitch (Vertical)", anchor="w").pack(padx=20, pady=(5,0), fill="x")
        self.pitch_slider = ctk.CTkSlider(self.sidebar, from_=-90, to=90, variable=self.pitch_offset, command=self.on_slider_drag)
        self.pitch_slider.bind("<ButtonRelease-1>", self.on_slider_release)
        self.pitch_slider.pack(padx=20, pady=5, fill="x")

        self.create_separator(self.sidebar, "Fixes")
        ctk.CTkCheckBox(self.sidebar, text="Flip Top/Bottom Faces", variable=self.flip_up, command=self.update_previews_only).pack(padx=20, pady=10, anchor="w")
        
        ctk.CTkButton(self.sidebar, text="Reset Transforms", fg_color="transparent", border_width=1, command=self.reset_settings).pack(padx=20, pady=10, fill="x")

        self.progress_bar = ctk.CTkProgressBar(self.sidebar, mode="indeterminate", height=10)
        self.progress_bar.pack(padx=20, pady=(20, 10), fill="x", side="bottom")
        self.progress_bar.set(0)
        
        self.save_btn = ctk.CTkButton(self.sidebar, text="EXPORT .PK3", command=self.save_pk3, state="disabled", height=50, font=ctk.CTkFont(weight="bold"))
        self.save_btn.pack(padx=20, pady=20, side="bottom", fill="x")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.preview_container = ctk.CTkFrame(self.main_frame, fg_color="#1a1a1a")
        self.preview_container.pack(fill="both", expand=True)
        
        self.grid_frame = ctk.CTkFrame(self.preview_container, fg_color="transparent")
        self.grid_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        self.preview_labels = {}
        positions = {"top": (0, 1), "left": (1, 0), "front": (1, 1), "right": (1, 2), "back": (1, 3), "bottom": (2, 1)}
        
        for face, pos in positions.items():
            f_frame = ctk.CTkFrame(self.grid_frame, border_width=0, corner_radius=0, fg_color="#333333")
            f_frame.grid(row=pos[0], column=pos[1], padx=2, pady=2)
            lbl = ctk.CTkLabel(f_frame, text=face.upper(), width=160, height=160, text_color="#666666")
            lbl.pack()
            self.preview_labels[face] = lbl
            
            if face in ["top", "bottom"]:
                btn = ctk.CTkButton(f_frame, text="↻", width=30, height=30, command=lambda f=face: self.rotate_face_logic(f))
                btn.place(relx=1.0, rely=0.0, anchor="ne")

        self.status_lbl = ctk.CTkLabel(self.main_frame, textvariable=self.status_var, anchor="w", text_color="#888888")
        self.status_lbl.pack(fill="x", pady=(5,0))

    def create_separator(self, parent, text):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(15, 5))
        ctk.CTkLabel(f, text=text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#aaaaaa").pack(side="left", padx=10)
        ctk.CTkFrame(f, height=2, fg_color="#444444").pack(side="left", fill="x", expand=True, padx=5)

    def create_labeled_entry(self, parent, text, variable):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f, text=text, width=70, anchor="w").pack(side="left")
        ctk.CTkEntry(f, textvariable=variable).pack(side="left", fill="x", expand=True)

    def toggle_quality_state(self, val):
        if val == "TGA":
            self.quality_slider.configure(state="disabled", button_color="#555555")
            self.quality_label.configure(text_color="#555555")
        else:
            self.quality_slider.configure(state="normal", button_color=["#3B8ED0", "#1F6AA5"])
            self.quality_label.configure(text_color=["gray10", "gray90"])
            self.update_quality_label(self.quality_var.get())

    def update_quality_label(self, val):
        if self.format_var.get() == "JPG":
            self.quality_label.configure(text=f"JPG Quality: {int(val)}")
        else:
            self.quality_label.configure(text="Quality: Lossless (TGA)")

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.tga *.bmp")])
        if not path: return
        try:
            self.status_var.set("Loading image...")
            self.save_btn.configure(state="disabled")
            
            pil_img = Image.open(path).convert("RGB")
            self.original_image = pil_img
            self.panorama_array = np.array(pil_img)
            
            name = os.path.splitext(os.path.basename(path))[0]
            self.prefix_var.set(name)
            self.pk3_name_var.set(name)
            
            self.status_var.set("Image loaded. Generating preview...")
            self.run_generation(preview_mode=True)
            self.trigger_high_res()
        except Exception as e:
            CTkMessagebox(title="Error", message=f"Failed to load image: {e}", icon="cancel")

    def on_slider_drag(self, val):
        if not self.panorama_array is None:
            self.status_var.set(f"Previewing Yaw: {self.yaw_offset.get():.1f} | Pitch: {self.pitch_offset.get():.1f}")
            if not self.is_processing:
                self.run_generation(preview_mode=True)

    def on_slider_release(self, event):
        self.trigger_high_res()

    def trigger_high_res(self, _=None):
        if self.panorama_array is not None:
            self.status_var.set("Rendering High Quality...")
            self.progress_bar.start()
            self.run_generation(preview_mode=False)

    def run_generation(self, preview_mode=False):
        threading.Thread(target=self._worker_process, args=(preview_mode,), daemon=True).start()

    def _worker_process(self, preview_mode):
        self.is_processing = True
        size = 256 if preview_mode else int(self.size_var.get())
        yaw, pitch = self.yaw_offset.get(), self.pitch_offset.get()
        faces = ["front", "back", "left", "right", "top", "bottom"]
        results = {}
        try:
            for face in faces:
                out_arr = ImageProcessor.remap_face(self.panorama_array, face, size, yaw, pitch)
                results[face] = Image.fromarray(out_arr)
            self.after(0, lambda: self._generation_complete(results, preview_mode))
        except Exception as e:
            self.is_processing = False

    def _generation_complete(self, results, preview_mode):
        self.is_processing = False
        if preview_mode:
            for face, img in results.items():
                self.preview_cache[face] = img.resize((160, 160), Image.Resampling.NEAREST)
        else:
            self.face_images = results
            for face, img in results.items():
                self.preview_cache[face] = img.resize((160, 160), Image.Resampling.LANCZOS)
            self.progress_bar.stop()
            self.status_var.set("Ready")
            self.save_btn.configure(state="normal")
        self.update_previews_only()

    def update_previews_only(self):
        if not self.preview_cache: return
        for face, label in self.preview_labels.items():
            if face in self.preview_cache:
                img = self.preview_cache[face]
                if face in ["top", "bottom"]:
                    if self.flip_up.get(): img = ImageOps.flip(img)
                    rot = self.face_rotations.get(face, 0)
                    if rot != 0: img = img.rotate(-rot)
                ctk_img = ctk.CTkImage(img, size=(160, 160))
                label.configure(image=ctk_img, text="")

    def rotate_face_logic(self, face):
        self.face_rotations[face] = (self.face_rotations[face] + 90) % 360
        self.update_previews_only()

    def reset_settings(self):
        self.yaw_offset.set(0)
        self.pitch_offset.set(0)
        self.face_rotations = {"top": 270, "bottom": 90}
        self.flip_up.set(True)
        self.trigger_high_res()

    def save_pk3(self):
        pk3_name = self.pk3_name_var.get().strip() or "skybox"
        
        save_path = filedialog.asksaveasfilename(
            initialfile=pk3_name,
            defaultextension=".pk3",
            filetypes=[("PK3 Archive", "*.pk3")]
        )
        
        if not save_path: return
        
        user_prefix = self.prefix_var.get().strip() or "sky"
        mapping = {"front":"ft", "back":"bk", "left":"lf", "right":"rt", "top":"up", "bottom":"dn"}
        export_fmt = self.format_var.get()
        file_ext = ".tga" if export_fmt == "TGA" else ".jpg"
        pil_fmt = "TGA" if export_fmt == "TGA" else "JPEG"
        jpg_q = self.quality_var.get()
        
        try:
            self.status_var.set("Compressing to PK3...")
            self.progress_bar.start()
            
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                
                for face, suffix in mapping.items():
                    if face not in self.face_images: continue
                    
                    img = self.face_images[face]
                    
                    if face in ["top", "bottom"]:
                        if self.flip_up.get(): img = ImageOps.flip(img)
                        if self.face_rotations[face] != 0: 
                            img = img.rotate(-self.face_rotations[face])
                    
                    img_buffer = io.BytesIO()
                    if pil_fmt == "JPEG":
                        img.save(img_buffer, format=pil_fmt, quality=jpg_q, subsampling=0)
                    else:
                        img.save(img_buffer, format=pil_fmt)
                    
                    archive_path = f"textures/skies/{user_prefix}_{suffix}{file_ext}"
                    zipf.writestr(archive_path, img_buffer.getvalue())

            self.progress_bar.stop()
            self.status_var.set("Export complete.")
            CTkMessagebox(title="Success", message=f"PK3 saved to:\n{save_path}", icon="check")
            
        except Exception as e:
            self.progress_bar.stop()
            self.status_var.set("Export failed.")
            CTkMessagebox(title="Error", message=f"Failed to create PK3: {e}", icon="cancel")

if __name__ == "__main__":
    app = SkyboxSmartFix()
    app.mainloop()