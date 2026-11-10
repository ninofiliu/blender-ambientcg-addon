bl_info = {
    "name": "AmbientCG Material Importer",
    "author": "Nino Filiu",
    "version": (1, 4, 0),
    "blender": (4, 2, 0),
    "location": "Shader Editor > Sidebar > AmbientCG",
    "description": "One-click material creation from AmbientCG",
    "category": "Material",
}

import bpy
import os
import threading
import urllib.request
import zipfile
from bpy.props import StringProperty, EnumProperty, FloatProperty
from pathlib import Path

# Global thread state tracking to prevent concurrent overlapping downloads/imports
_fetch_thread_running = False
_fetch_progress = 0.0
_fetch_status_msg = ""

class AmbientCGPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    cache_dir: StringProperty(
        name="Cache Folder",
        subtype="DIR_PATH",
        default=str(Path.home() / ".cache" / "ambientcg"),
        description="Directory where AmbientCG texture PNGs/JPGs will be stored",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "cache_dir")


def get_cache_dir():
    prefs: AmbientCGPreferences = bpy.context.preferences.addons[__name__].preferences
    dir_path = Path(prefs.cache_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def background_download_task(url, zip_path, extract_path, material_name, resolution):
    global _fetch_thread_running, _fetch_progress, _fetch_status_msg
    try:
        _fetch_status_msg = "Connecting to AmbientCG..."
        _fetch_progress = 10.0

        # Create a custom opener with a User-Agent
        opener = urllib.request.build_opener()
        opener.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            )
        ]
        urllib.request.install_opener(opener)

        _fetch_status_msg = f"Downloading {material_name} ({resolution})..."
        _fetch_progress = 30.0

        # Custom reporthook for urllib.request.urlretrieve progress tracking
        def download_progress_hook(block_num, block_size, total_size):
            global _fetch_progress, _fetch_status_msg
            if total_size > 0:
                downloaded = block_num * block_size
                percentage = min(70.0, 30.0 + (downloaded / total_size) * 40.0)
                _fetch_progress = percentage

        urllib.request.urlretrieve(url, zip_path, reporthook=download_progress_hook)

        _fetch_status_msg = "Extracting files..."
        _fetch_progress = 75.0

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        _fetch_progress = 90.0
        _fetch_status_msg = "Building material in Blender..."

    except Exception as e:
        _fetch_status_msg = f"Error: {str(e)}"
        print(f"[AmbientCG] Download/Extraction error: {e}")
        if zip_path.exists():
            zip_path.unlink()
        _fetch_thread_running = False
        return

    finally:
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass

    # Schedule the final Blender Node/Material creation safely on the Main Thread
    bpy.app.timers.register(lambda: create_material_main_thread(extract_path, material_name, resolution), first_interval=0.1)

def create_material_main_thread(extract_path, material_name, resolution):
    global _fetch_thread_running, _fetch_progress, _fetch_status_msg
    try:
        context = bpy.context
        fmt = context.scene.ambientcg_format
        fmt_lower = fmt.lower()
        detail_map_policy = context.scene.ambientcg_detail_map_policy
        projection_mode = context.scene.ambientcg_projection

        # Create a new material
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Clear default nodes
        nodes.clear()

        # Create shader nodes
        material_output = nodes.new(type="ShaderNodeOutputMaterial")
        material_output.location = (300, 0)

        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (0, 0)
        links.new(principled.outputs["BSDF"], material_output.inputs["Surface"])

        tex_coord = nodes.new(type="ShaderNodeTexCoord")
        tex_coord.location = (-1000, 0)

        mapping = nodes.new(type="ShaderNodeMapping")
        mapping.location = (-800, 0)

        blend_amt = 0.0
        if projection_mode == 'FLAT':
            links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
        else: 
            links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
            blend_amt = context.scene.ambientcg_blend

        # Find and load texture files
        for file in os.listdir(extract_path):
            if file.endswith(f"_Color.{fmt_lower}"):
                color_tex = nodes.new(type="ShaderNodeTexImage")
                color_tex.location = (-600, 600)
                color_tex.image = bpy.data.images.load(str(extract_path / file))
                color_tex.image.colorspace_settings.name = "sRGB"
                color_tex.projection = projection_mode
                color_tex.projection_blend = blend_amt
                links.new(color_tex.outputs["Color"], principled.inputs["Base Color"])
                links.new(mapping.outputs["Vector"], color_tex.inputs["Vector"])

            elif file.endswith(f"_Metalness.{fmt_lower}"):
                metalness_tex = nodes.new(type="ShaderNodeTexImage")
                metalness_tex.location = (-600, 300)
                metalness_tex.image = bpy.data.images.load(str(extract_path / file))
                metalness_tex.image.colorspace_settings.name = "Non-Color"
                metalness_tex.projection = projection_mode
                metalness_tex.projection_blend = blend_amt
                links.new(metalness_tex.outputs["Color"], principled.inputs["Metallic"])
                links.new(mapping.outputs["Vector"], metalness_tex.inputs["Vector"])

            elif file.endswith(f"_Roughness.{fmt_lower}"):
                roughness_tex = nodes.new(type="ShaderNodeTexImage")
                roughness_tex.location = (-600, 0)
                roughness_tex.image = bpy.data.images.load(str(extract_path / file))
                roughness_tex.image.colorspace_settings.name = "Non-Color"
                roughness_tex.projection = projection_mode
                roughness_tex.projection_blend = blend_amt
                links.new(roughness_tex.outputs["Color"], principled.inputs["Roughness"])
                links.new(mapping.outputs["Vector"], roughness_tex.inputs["Vector"])

            elif file.endswith(f"_NormalGL.{fmt_lower}") and (detail_map_policy in ("NORMAL", "BOTH")):
                normal_tex = nodes.new(type="ShaderNodeTexImage")
                normal_tex.location = (-600, -300)
                normal_tex.image = bpy.data.images.load(str(extract_path / file))
                normal_tex.image.colorspace_settings.name = "Non-Color"
                normal_tex.projection = projection_mode
                normal_tex.projection_blend = blend_amt
                normal_map = nodes.new(type="ShaderNodeNormalMap")
                normal_map.location = (-300, -300)
                links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
                links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
                links.new(mapping.outputs["Vector"], normal_tex.inputs["Vector"])

            elif file.endswith(f"_Displacement.{fmt_lower}") and (detail_map_policy in ("DISPLACEMENT", "BOTH")):
                displacement_tex = nodes.new(type="ShaderNodeTexImage")
                displacement_tex.location = (-600, -600)
                displacement_tex.image = bpy.data.images.load(str(extract_path / file))
                displacement_tex.image.colorspace_settings.name = "Non-Color"
                displacement_tex.projection = projection_mode
                displacement_tex.projection_blend = blend_amt
                displacement = nodes.new(type="ShaderNodeDisplacement")
                displacement.location = (-300, -600)
                links.new(displacement_tex.outputs["Color"], displacement.inputs["Height"])
                links.new(displacement.outputs["Displacement"], material_output.inputs["Displacement"])
                links.new(mapping.outputs["Vector"], displacement_tex.inputs["Vector"])

        _fetch_status_msg = f"Material '{material_name}' created successfully!"
        _fetch_progress = 100.0
        print(f"[AmbientCG] {_fetch_status_msg}")

    except Exception as e:
        _fetch_status_msg = f"Failed to build material: {str(e)}"
        print(f"[AmbientCG] {_fetch_status_msg}")

    finally:
        _fetch_thread_running = False
        # Force UI redraw to update button states
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

    return None  # Unregister timer

class MATERIAL_OT_fetch_and_create(bpy.types.Operator):
    bl_idname = "material.fetch_and_create"
    bl_label = "Fetch and Create Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        global _fetch_thread_running, _fetch_progress, _fetch_status_msg

        if _fetch_thread_running:
            self.report({"WARNING"}, "A material download is already in progress.")
            return {"CANCELLED"}

        material_name = context.scene.ambientcg_material_name
        resolution = context.scene.ambientcg_resolution
        fmt = context.scene.ambientcg_format
        fmt_lower = fmt.lower()

        url = f"https://ambientcg.com/get?file={material_name}_{resolution}-{fmt}.zip"
        cache_dir = get_cache_dir()
        extract_path = cache_dir / f"{material_name}_{resolution}"

        # Check if the cache folder exists and contains files of the selected format
        cache_valid = False
        if extract_path.is_dir():
            try:
                if any(file.lower().endswith(f".{fmt_lower}") for file in os.listdir(extract_path)):
                    cache_valid = True
            except Exception:
                pass

        if cache_valid:
            self.report(
                {"INFO"}, f"Using cached material: {material_name}_{resolution}"
            )
            # Cache is ready immediately, can run on main thread safely
            create_material_main_thread(extract_path, material_name, resolution)
            return {"FINISHED"}

        # Mark thread as running
        _fetch_thread_running = True
        _fetch_progress = 0.0
        _fetch_status_msg = "Initializing download..."

        zip_path = cache_dir / f"{material_name}_{resolution}.zip"

        # Spawn background worker thread to handle network I/O & extraction
        t = threading.Thread(
            target=background_download_task,
            args=(url, zip_path, extract_path, material_name, resolution)
        )
        t.daemon = True
        t.start()

        self.report({"INFO"}, f"Started background download for {material_name}...")
        return {"FINISHED"}


class MATERIAL_PT_ambientcg_fetcher(bpy.types.Panel):
    bl_label = "AmbientCG Fetcher"
    bl_idname = "MATERIAL_PT_ambientcg_fetcher"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "AmbientCG Fetcher"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "ambientcg_material_name", text="Material Name")
        layout.prop(scene, "ambientcg_format", text="Format", expand=True)
        layout.prop(scene, "ambientcg_resolution", text="Resolution")
        layout.prop(scene, "ambientcg_projection", text="Projection")
        layout.prop(scene, "ambientcg_detail_map_policy", text="Detail Map Policy")

        if(context.scene.ambientcg_projection == 'BOX'):
            layout.prop(scene, "ambientcg_blend", text="Blend", slider=True)

        # Dynamic UI feedback based on async execution state
        if _fetch_thread_running:
            layout.enabled = False
            row = layout.row()
            row.label(text=_fetch_status_msg, icon='FILE_CACHE')
            
            # Draw progress bar if supported by Blender version
            try:
                layout.prop(scene, "ambientcg_dummy_progress", text="", slider=True) # fallback or custom representation
            except Exception:
                pass
            
            # Display text percentage
            layout.label(text=f"Progress: {int(_fetch_progress)}%")
        else:
            layout.operator("material.fetch_and_create", icon='IMPORT')


classes = (
    AmbientCGPreferences,
    MATERIAL_OT_fetch_and_create,
    MATERIAL_PT_ambientcg_fetcher,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ambientcg_material_name = StringProperty(
        name="Material Name",
        description="Name of the AmbientCG material (e.g., Rock035)",
        default="Rock035",
    )
    bpy.types.Scene.ambientcg_resolution = EnumProperty(
        name="Resolution",
        description="Resolution of the material textures",
        items=[
            ("1K", "1K", "1K resolution"),
            ("2K", "2K", "2K resolution"),
            ("4K", "4K", "4K resolution"),
            ("8K", "8K", "8K resolution"),
        ],
        default="1K",
    )
    bpy.types.Scene.ambientcg_projection = EnumProperty(
        name="Projection Mode",
        description="Import mapping projection mode",
        items=[
            ('FLAT', "Flat (Default)", "Regular flat projection mapping"),
            ('BOX', "Box (Triplanar)", "Triplanar box projection mapping"),
            ('TUBE', "Cylinder", "Cylinder projection mapping"),
            ('SPHERE', "Sphere", "Sphere projection mapping"),
        ]
    )
    bpy.types.Scene.ambientcg_blend = FloatProperty(
        name="Blend",
        description="Blend amount for box projection",
        soft_min=0.0,
        soft_max=1.0,
        default=1.0,
    )

    bpy.types.Scene.ambientcg_format = EnumProperty(
        name="Format",
        description="Format to download in",
        items=[
            ("PNG", "PNG", "PNG Format (Higher quality, larger files)"),
            ("JPG", "JPG", "JPG Format (Lower quality, smaller files)")
        ],
        default="PNG",
    )

    bpy.types.Scene.ambientcg_detail_map_policy = EnumProperty(
        name="Detail Map Policy",
        description="Normal vs Displacement usage",
        items=[
            ("BOTH", "Both", "Use both normal and displacement maps"),
            ("NORMAL", "Normal Only", "Use only normal map"),
            ("DISPLACEMENT", "Displacement Only", "Use only displacement map"),
            ("NONE", "None", "Use neither normal and displacement maps")
        ],
        default="BOTH",
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ambientcg_material_name
    del bpy.types.Scene.ambientcg_resolution
    del bpy.types.Scene.ambientcg_projection
    del bpy.types.Scene.ambientcg_blend
    del bpy.types.Scene.ambientcg_format
    del bpy.types.Scene.ambientcg_detail_map_policy


if __name__ == "__main__":
    register()
