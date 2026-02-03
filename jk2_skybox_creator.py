import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from tkinter import filedialog
from PIL import Image, ImageOps
import os
import numpy as np

class SkyboxSmartFix:
    def __init__(self, root):
        self.root = root
        self.root.title("JK2 Skybox Creator | by flate8954")
        self.root.geometry("1200x950")
        
        self.panorama_image = None
        self.face_images = {}
        
        # Align with jk2s coordinate system
        self.face_rotations = {"top": 270, "bottom": 90}
        self.flip_up = ctk.BooleanVar(value=True)  # Should be on by default so we don't have to click it each time (we're lazy)
        
        self.prefix_var = ctk.StringVar(value="sky")
        self.size_var = ctk.StringVar(value="1024")
        self.yaw_offset = ctk.DoubleVar(value=0)
        self.pitch_offset = ctk.DoubleVar(value=0)

        self.setup_ui()

    def setup_ui(self):
        header = ctk.CTkFrame(self.root)
        header.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkButton(header, text="Import Image", command=self.load_image).pack(side="left", padx=5)
        
        ctk.CTkLabel(header, text="Prefix:").pack(side="left", padx=(10, 2))
        self.prefix_entry = ctk.CTkEntry(header, textvariable=self.prefix_var, width=120)
        self.prefix_entry.pack(side="left", padx=5)

        ctk.CTkLabel(header, text="Size:").pack(side="left", padx=(10, 2))
        self.size_menu = ctk.CTkOptionMenu(header, values=["512", "1024", "2048", "4096"], 
                                          variable=self.size_var, command=self.process_math, width=100)
        self.size_menu.pack(side="left", padx=5)

        ctk.CTkLabel(header, text="Yaw (↔):").pack(side="left", padx=(10, 2))
        self.yaw_slider = ctk.CTkSlider(header, from_=-180, to=180, variable=self.yaw_offset, 
                                        command=self.process_math, width=150)
        self.yaw_slider.pack(side="left", padx=5)

        ctk.CTkLabel(header, text="Pitch (↕):").pack(side="left", padx=(10, 2))
        self.pitch_slider = ctk.CTkSlider(header, from_=-90, to=90, variable=self.pitch_offset, 
                                          command=self.process_math, width=150)
        self.pitch_slider.pack(side="left", padx=5)

        ctk.CTkCheckBox(header, text="Flip UP/DN", variable=self.flip_up, command=self.update_previews).pack(side="left", padx=15)
        ctk.CTkButton(header, text="Reset", width=60, fg_color="#444444", command=self.reset_settings).pack(side="right", padx=5)

        self.scroll = ctk.CTkScrollableFrame(self.root, height=600)
        self.scroll.pack(pady=10, padx=20, fill="both", expand=True)
        self.previews = {}
        
        grid = {"top": (0, 1), "left": (1, 0), "front": (1, 1), "right": (1, 2), "back": (1, 3), "bottom": (2, 1)}
        for face, pos in grid.items():
            f = ctk.CTkFrame(self.scroll, border_width=1)
            f.grid(row=pos[0], column=pos[1], padx=10, pady=10)
            self.previews[face] = ctk.CTkLabel(f, text=face.upper(), width=180, height=180, fg_color="black")
            self.previews[face].pack(padx=2, pady=2)
            
            # We should only need top and bottom here
            if face in ["top", "bottom"]:
                ctk.CTkButton(f, text="Rotate 90", width=80, command=lambda f=face: self.rotate(f)).pack()

        self.save_btn = ctk.CTkButton(self.root, text="Export", command=self.save, state="disabled", height=50)
        self.save_btn.pack(pady=20)

    def reset_settings(self):
        self.yaw_offset.set(0)
        self.pitch_offset.set(0)
        self.face_rotations = {"top": 270, "bottom": 90}
        self.flip_up.set(True)
        if self.panorama_image: self.process_math()

    def rotate(self, face):
        self.face_rotations[face] = (self.face_rotations[face] + 90) % 360
        self.update_previews()

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.tga")])
        if path:
            self.panorama_image = Image.open(path).convert("RGB")
            self.prefix_var.set(os.path.splitext(os.path.basename(path))[0])
            self.process_math()

    # Convert equirectangular into cartesian
    def process_math(self, _=None):
        if not self.panorama_image: return
        
        size = int(self.size_var.get())
        img = np.array(self.panorama_image).astype(np.float32)
        h_pan, w_pan, _ = img.shape
        
        # Handle non-2:1 aspect ratio images (this is going to look ugly ingame but lets support it either way)
        current_ratio = w_pan / h_pan
        ratio_scale = current_ratio / 2.0 

        # Degrees to radians
        yaw = np.radians(self.yaw_offset.get())
        pitch = np.radians(self.pitch_offset.get())
        
        for face in ["front", "back", "left", "right", "top", "bottom"]:
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

            # X-axis - pitch
            nx = vx * np.cos(pitch) + vz * np.sin(pitch)
            ny = vy
            nz = -vx * np.sin(pitch) + vz * np.cos(pitch)

            # Z-axis - yaw
            rx = nx * np.cos(yaw) - ny * np.sin(yaw)
            ry = nx * np.sin(yaw) + ny * np.cos(yaw)
            rz = nz

            mag = np.sqrt(rx**2 + ry**2 + rz**2)
            phi = np.arctan2(ry, rx)
            theta = np.arcsin(rz / mag)
            
            ui = (phi + np.pi) / (2 * np.pi) * (w_pan - 1)
            vi = (np.pi/2 - theta * (1/ratio_scale)) / np.pi * (h_pan - 1)
            
            # Try to prevent edge sampling errors
            ui = np.clip(ui, 0, w_pan - 1)
            vi = np.clip(vi, 0, h_pan - 1)
            
            # Bilinear interpolation
            u0, v0 = np.floor(ui).astype(int), np.floor(vi).astype(int)
            u1, v1 = (u0 + 1) % w_pan, (v0 + 1) % h_pan
            du, dv = (ui - u0)[..., None], (vi - v0)[..., None]
            
            out = (img[v0, u0]*(1-du)*(1-dv) + img[v0, u1]*du*(1-dv) + 
                   img[v1, u0]*(1-du)*dv + img[v1, u1]*du*dv)
            
            self.face_images[face] = Image.fromarray(out.astype(np.uint8))
            
        self.update_previews()
        self.save_btn.configure(state="normal")

    # This is going to be a bit slow and probably make the application feel stuck but whatever, here goes
    def update_previews(self):
        for face, img in self.face_images.items():
            display = img
            if face in ["top", "bottom"]:
                if self.flip_up.get(): display = ImageOps.flip(display)
                if self.face_rotations[face] != 0: 
                    display = display.rotate(-self.face_rotations[face])
            
            p = ctk.CTkImage(display, size=(180, 180))
            self.previews[face].configure(image=p, text="")

    def save(self):
        folder = filedialog.askdirectory()
        if not folder: return
        
        user_prefix = self.prefix_var.get().strip() or "sky"
        mapping = {"front":"ft", "back":"bk", "left":"lf", "right":"rt", "top":"up", "bottom":"dn"}
        
        for face, suffix in mapping.items():
            img = self.face_images[face]
            
            if face in ["top", "bottom"]:
                if self.flip_up.get(): img = ImageOps.flip(img)
                if self.face_rotations[face] != 0: 
                    img = img.rotate(-self.face_rotations[face])
            
            # Save with max quality
            filename = f"{user_prefix}_{suffix}.jpg"
            img.save(os.path.join(folder, filename), quality=100, subsampling=0)
            
        CTkMessagebox(title="Success", message=f"Exported to:\n{folder}")

if __name__ == "__main__":
    app = SkyboxSmartFix(ctk.CTk())
    app.root.mainloop()