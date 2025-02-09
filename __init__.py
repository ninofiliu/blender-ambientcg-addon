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
import urllib.request
import zipfile
from bpy.props import StringProperty, EnumProperty
from pathlib import Path


class AmbientCGPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    cache_dir: StringProperty(
        name="Cache Folder",
        subtype="DIR_PATH",
        default=str(Path.home() / ".cache" / "ambientcg"),
        description="Directory where AmbientCG texture PNGs will be stored",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "cache_dir")


def get_cache_dir():
    prefs: AmbientCGPreferences = bpy.context.preferences.addons[__name__].preferences
    dir_path = Path(prefs.cache_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


class MATERIAL_OT_fetch_and_create(bpy.types.Operator):
    bl_idname = "material.fetch_and_create"
    bl_label = "Fetch and Create Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        material_name = context.scene.ambientcg_material_name
        resolution = context.scene.ambientcg_resolution

        url = f"https://ambientcg.com/get?file={material_name}_{resolution}-PNG.zip"

        cache_dir = get_cache_dir()
        extract_path = cache_dir / f"{material_name}_{resolution}"

        if not extract_path.exists():
            # Download and extract the zip file
            zip_path = cache_dir / f"{material_name}_{resolution}.zip"

            # Create a custom opener with a User-Agent
            opener = urllib.request.build_opener()
            opener.addheaders = [
                (
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                )
            ]
            urllib.request.install_opener(opener)

            # Download the file
            try:
                urllib.request.urlretrieve(url, zip_path)
            except Exception as e:
                self.report({"ERROR"}, f"Failed to download file: {str(e)}")
                return {"CANCELLED"}

            # Extract the zip file
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(extract_path)
                zip_path.unlink()  # Remove the zip file after extraction
            except Exception as e:
                self.report({"ERROR"}, f"Failed to extract zip file: {str(e)}")
                return {"CANCELLED"}
        else:
            self.report(
                {"INFO"}, f"Using cached material: {material_name}_{resolution}"
            )

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

        # Creating a Texture Coordinate Node and a Mapping Node
        tex_coord = nodes.new(type="ShaderNodeTexCoord")
        tex_coord.location = (-1000, 0)

        mapping = nodes.new(type="ShaderNodeMapping")
        mapping.location = (-800, 0)
        links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

        # Find and load texture files
        for file in os.listdir(extract_path):
            if file.endswith("_Color.png"):
                color_tex = nodes.new(type="ShaderNodeTexImage")
                color_tex.location = (-600, 600)
                color_tex.image = bpy.data.images.load(str(extract_path / file))
                color_tex.image.colorspace_settings.name = "sRGB"
                links.new(color_tex.outputs["Color"], principled.inputs["Base Color"])
                links.new(mapping.outputs["Vector"], color_tex.inputs["Vector"])
            elif file.endswith("_Metalness.png"):
                metalness_tex = nodes.new(type="ShaderNodeTexImage")
                metalness_tex.location = (-600, 300)
                metalness_tex.image = bpy.data.images.load(str(extract_path / file))
                metalness_tex.image.colorspace_settings.name = "Non-Color"
                links.new(metalness_tex.outputs["Color"], principled.inputs["Metallic"])
                links.new(mapping.outputs["Vector"], metalness_tex.inputs["Vector"])
            elif file.endswith("_Roughness.png"):
                roughness_tex = nodes.new(type="ShaderNodeTexImage")
                roughness_tex.location = (-600, 0)
                roughness_tex.image = bpy.data.images.load(str(extract_path / file))
                roughness_tex.image.colorspace_settings.name = "Non-Color"
                links.new(
                    roughness_tex.outputs["Color"], principled.inputs["Roughness"]
                )
                links.new(mapping.outputs["Vector"], roughness_tex.inputs["Vector"])
            elif file.endswith("_NormalGL.png"):
                normal_tex = nodes.new(type="ShaderNodeTexImage")
                normal_tex.location = (-600, -300)
                normal_tex.image = bpy.data.images.load(str(extract_path / file))
                normal_tex.image.colorspace_settings.name = "Non-Color"
                normal_map = nodes.new(type="ShaderNodeNormalMap")
                normal_map.location = (-300, -300)
                links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
                links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
                links.new(mapping.outputs["Vector"], normal_tex.inputs["Vector"])
            elif file.endswith("_Displacement.png"):
                displacement_tex = nodes.new(type="ShaderNodeTexImage")
                displacement_tex.location = (-600, -600)
                displacement_tex.image = bpy.data.images.load(str(extract_path / file))
                displacement_tex.image.colorspace_settings.name = "Non-Color"
                displacement = nodes.new(type="ShaderNodeDisplacement")
                displacement.location = (-300, -600)
                links.new(
                    displacement_tex.outputs["Color"], displacement.inputs["Height"]
                )
                links.new(
                    displacement.outputs["Displacement"],
                    material_output.inputs["Displacement"],
                )
                links.new(mapping.outputs["Vector"], displacement_tex.inputs["Vector"])

        self.report(
            {"INFO"}, f"Material '{material_name}' has been created successfully."
        )
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
        layout.prop(scene, "ambientcg_resolution", text="Resolution")
        layout.operator("material.fetch_and_create")


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


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ambientcg_material_name
    del bpy.types.Scene.ambientcg_resolution


if __name__ == "__main__":
    register()
