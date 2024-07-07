# Blender AmbientCG Addon

One-click material creation from AmbientCG

## Installation

Download ZIP

![image](https://github.com/ninofiliu/blender-ambientcg-addon/assets/29477588/a5927fb2-f985-48a9-a3d6-133e0f946224)

Open blender, go to Edit > Preferences > Addons

Click on install and select the downloaded zip file

![image](https://github.com/ninofiliu/blender-ambientcg-addon/assets/29477588/5ed434f5-64f1-4966-a9af-a6621c0d705d)

![image](https://github.com/ninofiliu/blender-ambientcg-addon/assets/29477588/24e964e2-9e25-4633-93c9-449f4ccbd3cb)

Finally, enable it by checking the checkbox

## Usage

Once the addon has been installed and enabled, there should be a new side tab in the shader editor

![image](https://github.com/ninofiliu/blender-ambientcg-addon/assets/29477588/3e37f5e5-5f15-43af-89ca-753a95c86b17)

Fill in the material name and the resolution. By default, it fills in [Rock035](https://ambientcg.com/view?id=Rock035), but you can chose any other material id. The material id is basically the displayed material name without space, as it appears in the URL.

![image](https://github.com/ninofiliu/blender-ambientcg-addon/assets/29477588/413cced7-ee3a-4d19-a6b9-c91c9aa5d3a5)

Click on `Fetch and Create Material`. Wait for the material to be fetched - depending on the resolution and your connection, it should take anywhere from 5s to 1mn. You'll then be able to select the material from the dropdown. It set up the color texture, the roughness, and the metalness.

![image](https://github.com/ninofiliu/blender-ambientcg-addon/assets/29477588/84271a37-c989-4767-981b-21224199d7bc)

Note that downloads are cached to `<home>/.cache/ambientcg` (for example, on windows, if your username is `nino`, downloads are cached in `C:\Users\nino\.cache\ambientcg`, and on unix, `/home/nino/.cache/ambientcg`), so if you already downloaded the texture, even in another blender file, it should skip the download this time!

---

Made with <3 by [Nino Filiu](https://ninofiliu.com/)
