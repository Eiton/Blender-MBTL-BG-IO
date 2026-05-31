bl_info = {
   "name": "MBTL fbx.json Format",
   "author": "Eiton",
   "version": (1, 1, 0),
   "blender": (4, 0, 0),
   "location": "File > Import-Export",
   "description": "Import / Export files Melty Blood Type Lumina BG file",
   "category": "Import-Export"}

import bpy
import os
import json
import shutil
import struct
import mathutils
import math
from bpy.props import BoolProperty, FloatProperty, StringProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

class ImportJSON(bpy.types.Operator, ImportHelper):
   bl_idname = "import_scene_fbx.json"
   bl_label = 'Import MBTL (*.json)'
   bl_options = {'UNDO'}
   filename_ext = ".json"
   
   filter_glob: StringProperty(default="*.json", options={'HIDDEN'}, maxlen=255)
   
   def draw(self, context):
      layout = self.layout

   def execute(self, context):
      path = os.path.normpath(self.filepath)
      with open(path, 'rb') as f:
        data = json.load(f)
        parentMap = {}
        materials = []
        for i in range(data["fbxex"]["material"]["count"]):
            material = data["fbxex"]["material"][str(i)]
            mat = bpy.data.materials.new("mat_"+str(i))  
            mat.use_nodes = True            
            mat.use_backface_culling = False
            mat.show_transparent_back = False
            nodes = mat.node_tree.nodes
            nodes.clear()
            tex = nodes.new('ShaderNodeTexImage')
            imagePath = path[:path.rfind("\\")+1]+material["filename"]
            if imagePath[len(imagePath)-3:] == "psd":
                imagePath = imagePath[:len(imagePath)-3]+"dds" 
            tex.image = bpy.data.images.load(imagePath, check_existing=True)
            tex.image.colorspace_settings.is_data = False
            if image_has_alpha(tex.image):
                mat.blend_method = "BLEND"
            pbsdf = nodes.new('ShaderNodeBsdfPrincipled')
            
            attr = nodes.new('ShaderNodeAttribute')
            attr.attribute_type = 'OBJECT'
            attr.attribute_name = 'dst'
            tbsdf = nodes.new('ShaderNodeBsdfTransparent')
            
            addShader = nodes.new('ShaderNodeAddShader')
            
            output = nodes.new('ShaderNodeOutputMaterial')
            output.target = "ALL"
            
            links = mat.node_tree.links
            link = links.new(tex.outputs[0], pbsdf.inputs[0])
            link = links.new(tex.outputs[1], pbsdf.inputs[4])
            link = links.new(pbsdf.outputs[0], addShader.inputs[0])
            link = links.new(attr.outputs[0], tbsdf.inputs[0])
            link = links.new(tbsdf.outputs[0], addShader.inputs[1])
            
            link = links.new(addShader.outputs[0], output.inputs[0])
            materials.append(mat)
        total_frames = 0
        for i in range(data["fbxex"]["anime"]["count"]):
            total_frames = max(total_frames,data["fbxex"]["anime"][str(i)][0])
        bpy.context.scene.render.fps = 60
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_end = total_frames
        bpy.context.scene.frame_current = 0
        root = bpy.data.objects.new( "root", None)
        bpy.context.collection.objects.link(root)
        root.rotation_euler = mathutils.Euler((1.5707963705062866, 0.0, 0), 'XYZ')
        root.scale = (1,1,1)
      
        for i in range(data["fbxex"]["node"]["count"]):
            n = data["fbxex"]["node"][str(i)]
            parentMap[str(n["child"])] = format(i,'04d')
            mat = mathutils.Matrix()
            if "matrix" in n:
                m = n["matrix"]
                mat = mathutils.Matrix(((m[0],m[1],m[2],m[3]),(m[4],m[5],m[6],m[7]),(m[8],m[9],m[10],m[11]),(m[12],m[13],m[14],m[15])))
                mat.transpose()
            if str(i) in parentMap and n["sibling"] != -1:
                parentMap[str(n["sibling"])] = parentMap[str(i)]
            if n["type"] == 0:
                new_object = bpy.data.objects.new(format(i,'04d'), None)
                applyTransform(mat,new_object)
                bpy.context.collection.objects.link(new_object)
                if str(i) in parentMap:
                    new_object.parent = bpy.context.collection.objects[parentMap[str(i)]]
                else:
                    new_object.parent = root
            if n["type"] == 1:
                vs = n["vertex"]
                vertices = []
                #no need
                #normals = []
                uvs = []
                for j in range(vs["count"]):
                    v = vs[str(j)]
                    vertices.append((v[0],v[1],v[2]))
                    #no need as blender generates the normal automatically
                    #normals.append((v[3],v[4],v[5]))
                    uvs.append((v[10],v[11]))
                indices = []
                for j in range(int(n["material"]["0"]["vertexindexcount"]//3)):
                    indices.append((n["material"]["0"]["vertexindex"][j*3],n["material"]["0"]["vertexindex"][j*3+1],n["material"]["0"]["vertexindex"][j*3+2]))
                mesh = bpy.data.meshes.new(format(i,'04d'))
                mesh.from_pydata(vertices, [], indices)
                mesh.update()
                new_object = bpy.data.objects.new(format(i,'04d'), mesh)
                applyTransform(mat,new_object)
                new_object.data = mesh                    
                bpy.context.collection.objects.link(new_object)
                if str(i) in parentMap:
                    new_object.parent = bpy.context.collection.objects[parentMap[str(i)]]
                else:
                    new_object.parent = root
                mesh.vertex_colors.new(name="vert_colors")
                color_layer = mesh.vertex_colors["vert_colors"]
                indices_f = list(sum(indices, ()))
                for j in range(len(color_layer.data)):
                    v = vs[str(indices_f[j])]
                    color_layer.data[j].color = [v[6],v[7],v[8],v[9]]
                mesh.uv_layers.new(name="uv")
                uv_layer = mesh.uv_layers["uv"]
                for j in range(len(uv_layer.data)):
                    v = vs[str(indices_f[j])]
                    uv_layer.data[j].uv = [v[10],v[11]]
                new_object.data.materials.append(materials[n["material"]["0"]["index"]])
                if n["blendmode"] == 1:
                    new_object["trans"] = "ADD"
                    new_object["dst"] = 1
            if data["fbxex"]["anime"][str(i)][0] > 0:
                new_object.animation_data_create()
                new_object.animation_data.action = bpy.data.actions.new(name="anim")
                fcurves = new_object.animation_data.action.fcurves
                fcurves.new(data_path="location",index=0)
                fcurves.new(data_path="location",index=1)
                fcurves.new(data_path="location",index=2)
                fcurves.new(data_path="rotation_euler",index=0)
                fcurves.new(data_path="rotation_euler",index=1)
                fcurves.new(data_path="rotation_euler",index=2)
                fcurves.new(data_path="scale",index=0)
                fcurves.new(data_path="scale",index=1)
                fcurves.new(data_path="scale",index=2)
                for j in range(data["fbxex"]["anime"][str(i)][0]):
                    m = data["fbxex"]["anime"][str(i)][(1+j*16):(1+(j+1)*16)]
                    mat = mathutils.Matrix(((m[0],m[1],m[2],m[3]),(m[4],m[5],m[6],m[7]),(m[8],m[9],m[10],m[11]),(m[12],m[13],m[14],m[15])))
                    mat.transpose()
                    (x,y,z) = mat.to_translation()
                    k = fcurves[0].keyframe_points.insert(frame=j,value=x)
                    k.interpolation = "CONSTANT"
                    k = fcurves[1].keyframe_points.insert(frame=j,value=y)
                    k.interpolation = "CONSTANT"
                    k = fcurves[2].keyframe_points.insert(frame=j,value=z)
                    k.interpolation = "CONSTANT"
                    (x,y,z) = mat.to_euler()
                    k = fcurves[3].keyframe_points.insert(frame=j,value=x)
                    k.interpolation = "CONSTANT"
                    k = fcurves[4].keyframe_points.insert(frame=j,value=y)
                    k.interpolation = "CONSTANT"
                    k = fcurves[5].keyframe_points.insert(frame=j,value=z)
                    k.interpolation = "CONSTANT"
                    (x,y,z) = mat.to_scale()
                    k = fcurves[6].keyframe_points.insert(frame=j,value=x)
                    k.interpolation = "CONSTANT"
                    k = fcurves[7].keyframe_points.insert(frame=j,value=y)
                    k.interpolation = "CONSTANT"
                    k = fcurves[8].keyframe_points.insert(frame=j,value=z)
                    k.interpolation = "CONSTANT"
      return {'FINISHED'}


class ExportBin(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene_fbx.fbx_bin"
    bl_label = 'Export MBTL (*.bin)'
    bl_options = {'UNDO'}
    filename_ext = ".bin"

    filter_glob: StringProperty(default="*.bin", options={'HIDDEN'}, maxlen=255)
    export_all_objects: BoolProperty(
        name="Export All Objects",
        description="Export all supported objects in the scene instead of only selected objects",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_all_objects")

    def execute(self, context):
        export_path = os.path.normpath(self.filepath)
        export_dir = os.path.dirname(export_path)
        export_objects = collect_export_objects(get_export_source_objects(context, self.export_all_objects))

        if not export_objects:
            self.report({'ERROR'}, "No supported objects found to export")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        scene = context.scene
        original_frame = scene.frame_current
        placeholder_image = None

        try:
            os.makedirs(export_dir, exist_ok=True)
            material_records, object_material_indices, placeholder_image = collect_export_materials(export_objects)
            export_texture_images(material_records, export_dir)

            export_lookup = set(export_objects)
            node_payload = build_export_node_payload(export_objects, export_lookup, object_material_indices, depsgraph)
            anime_payload = build_export_anime_payload(export_objects, export_lookup, scene)

            payload = {
                "fbxex": {
                    "material": build_export_material_payload(material_records),
                    "anime": anime_payload,
                    "node": node_payload,
                }
            }

            #with open(export_path, 'w', encoding='utf-8') as handle:
            #    json.dump(payload, handle, indent=2)
            #    handle.write("\n")
            #binary_path = os.path.splitext(export_path)[0] + ".bin"
            convert_to_fbxex_binary(payload, export_path)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        finally:
            scene.frame_set(original_frame)
            if placeholder_image is not None and placeholder_image.users == 0:
                bpy.data.images.remove(placeholder_image)

        export_msg = f"Exported {len(export_objects)} objects to {os.path.basename(export_path)}"
        self.report({'INFO'}, export_msg)
        return {'FINISHED'}


def applyTransform(mat,obj):
    obj.location = mat.to_translation()
    obj.rotation_euler = mat.to_euler()
    obj.scale = mat.to_scale()


def image_has_alpha(img):
    b = 32 if img.is_float else 8
    return (
        img.depth == 2*b or   # Grayscale+Alpha
        img.depth == 4*b      # RGB+Alpha
    )


def collect_export_objects(selected_objects):
    selected = list(selected_objects)
    if not selected:
        return []

    selected_lookup = set(selected)
    ordered = []
    seen = set()

    def sort_key(obj):
        return (obj.name_full.lower(), obj.as_pointer())

    def visit(obj):
        if obj in seen:
            return
        seen.add(obj)
        ordered.append(obj)
        children = sorted([child for child in obj.children if child in selected_lookup], key=sort_key)
        for child in children:
            visit(child)

    roots = sorted([obj for obj in selected if obj.parent not in selected_lookup], key=sort_key)
    for root in roots:
        visit(root)

    for obj in sorted(selected, key=sort_key):
        visit(obj)

    return ordered


def get_export_source_objects(context, export_all_objects):
    if export_all_objects:
        return [obj for obj in context.scene.objects if obj.type in ('MESH', 'EMPTY')]
    return [obj for obj in context.selected_objects if obj.type in ('MESH', 'EMPTY')]


def collect_export_materials(export_objects):
    material_records = []
    material_lookup = {}
    object_material_indices = {}
    used_filenames = set()
    placeholder_image = None

    for obj in export_objects:
        if obj.type != 'MESH':
            continue

        material = get_primary_material(obj)
        image = get_material_image(material)
        if image is None:
            if placeholder_image is None:
                placeholder_image = create_placeholder_image()
            image = placeholder_image

        key = image.as_pointer()
        if key not in material_lookup:
            filename = make_unique_dds_name(image, used_filenames)
            material_lookup[key] = len(material_records)
            material_records.append({"image": image, "filename": filename})

        object_material_indices[obj] = material_lookup[key]

    return material_records, object_material_indices, placeholder_image


def build_export_material_payload(material_records):
    payload = {"count": len(material_records)}
    for index, record in enumerate(material_records):
        payload[str(index)] = {"filename": record["filename"]}
    return payload


def build_export_node_payload(export_objects, export_lookup, object_material_indices, depsgraph):
    index_map = {obj: index for index, obj in enumerate(export_objects)}
    child_map = {obj: [] for obj in export_objects}
    node_entries = []

    for obj in export_objects:
        if obj.parent in export_lookup:
            child_map[obj.parent].append(obj)

    for obj in export_objects:
        node = {
            "child": -1,
            "sibling": -1,
            "type": 1 if obj.type == 'MESH' else 0,
            "matrix": flatten_export_matrix(get_object_export_matrix(obj, export_lookup)),
        }

        if obj.type == 'MESH':
            node.update(serialize_export_mesh(obj, depsgraph, object_material_indices.get(obj, 0)))

        node_entries.append(node)

    for parent, children in child_map.items():
        if not children:
            continue

        node_entries[index_map[parent]]["child"] = index_map[children[0]]
        for current, following in zip(children, children[1:]):
            node_entries[index_map[current]]["sibling"] = index_map[following]

    payload = {"count": len(node_entries)}
    for index, node in enumerate(node_entries):
        payload[str(index)] = node
    return payload


def build_export_anime_payload(export_objects, export_lookup, scene):
    frame_start = scene.frame_start
    frame_end = max(frame_start, scene.frame_end)
    frame_count = frame_end - frame_start + 1
    payload = {"count": len(export_objects)}

    for index, obj in enumerate(export_objects):
        track = [frame_count]
        for frame in range(frame_start, frame_end + 1):
            scene.frame_set(frame)
            track.extend(flatten_export_matrix(get_object_export_matrix(obj, export_lookup)))
        payload[str(index)] = track

    return payload


def serialize_export_mesh(obj, depsgraph, material_index):
    evaluated_object = obj.evaluated_get(depsgraph)
    mesh = evaluated_object.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

    try:
        mesh.calc_loop_triangles()
        if hasattr(mesh, "calc_normals_split"):
            mesh.calc_normals_split()

        uv_data = mesh.uv_layers.active.data if mesh.uv_layers.active else None
        color_data = get_active_color_data(mesh)
        vertex_payload = {"count": 0}
        vertex_indices = []
        vertex_index = 0

        for triangle in mesh.loop_triangles:
            for loop_index in triangle.loops:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                color = get_loop_color(color_data, loop_index)
                uv = uv_data[loop_index].uv if uv_data else (0.0, 0.0)
                normal = loop.normal if hasattr(loop, "normal") else vertex.normal

                vertex_payload[str(vertex_index)] = [
                    float(vertex.co.x),
                    float(vertex.co.y),
                    float(vertex.co.z),
                    float(normal.x),
                    float(normal.y),
                    float(normal.z),
                    float(color[0]),
                    float(color[1]),
                    float(color[2]),
                    float(color[3]),
                    float(uv[0]),
                    float(uv[1]),
                ]
                vertex_indices.append(vertex_index)
                vertex_index += 1

        vertex_payload["count"] = vertex_index
        return {
            "vertex": vertex_payload,
            "material": {
                "0": {
                    "index": material_index,
                    "vertexindexcount": len(vertex_indices),
                    "vertexindex": vertex_indices,
                }
            },
            "blendmode": 1 if obj.get("trans") == "ADD" else 0,
        }
    finally:
        evaluated_object.to_mesh_clear()


def get_active_color_data(mesh):
    if hasattr(mesh, "color_attributes") and len(mesh.color_attributes) > 0:
        color_attribute = mesh.color_attributes.active_color or mesh.color_attributes.active
        if color_attribute is not None and color_attribute.domain == 'CORNER':
            return color_attribute.data

    if hasattr(mesh, "vertex_colors") and mesh.vertex_colors.active is not None:
        return mesh.vertex_colors.active.data

    return None


def get_loop_color(color_data, loop_index):
    if color_data is None:
        return (1.0, 1.0, 1.0, 1.0)

    color = color_data[loop_index].color
    if len(color) == 4:
        return color
    return (color[0], color[1], color[2], 1.0)


def get_primary_material(obj):
    for slot in obj.material_slots:
        if slot.material is not None:
            return slot.material
    return None


def get_material_image(material):
    if material is None or not material.use_nodes or material.node_tree is None:
        return None

    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image is not None:
            return node.image
    return None


def create_placeholder_image():
    image = bpy.data.images.new("MBTL_Default", 1, 1, alpha=True)
    image.generated_color = (1.0, 1.0, 1.0, 1.0)
    return image


def make_unique_dds_name(image, used_filenames):
    source_name = image.name
    if image.filepath:
        source_name = os.path.basename(bpy.path.abspath(image.filepath, library=image.library))

    stem, _ = os.path.splitext(source_name)
    stem = sanitize_export_name(stem or "texture")
    candidate = f"{stem}.dds"
    suffix = 1

    while candidate.lower() in used_filenames:
        candidate = f"{stem}_{suffix}.dds"
        suffix += 1

    used_filenames.add(candidate.lower())
    return candidate


def sanitize_export_name(value):
    sanitized = []
    for char in value:
        if char.isalnum() or char in ('_', '-', '.'):
            sanitized.append(char)
        else:
            sanitized.append('_')
    return ''.join(sanitized).strip('._') or "texture"


def export_texture_images(material_records, export_dir):
    for record in material_records:
        image = record["image"]
        target_path = os.path.join(export_dir, record["filename"])
        export_texture_image(image, target_path)


def export_texture_image(image, target_path):
    source_path = bpy.path.abspath(image.filepath, library=image.library) if image.filepath else ""
    if source_path and os.path.isfile(source_path):
        source_abs = os.path.abspath(source_path)
        target_abs = os.path.abspath(target_path)
        if os.path.normcase(source_abs) != os.path.normcase(target_abs):
            shutil.copyfile(source_abs, target_abs)
        return

    temp_image = image.copy()
    try:
        temp_image.filepath_raw = target_path
        temp_image.file_format = image.file_format if image.file_format else 'PNG'
        temp_image.save()
    except Exception as exc:
        raise RuntimeError(f"Failed to export texture '{image.name}': {exc}") from exc
    finally:
        bpy.data.images.remove(temp_image)


def get_object_export_matrix(obj, export_lookup):
    if obj.parent in export_lookup:
        return obj.matrix_local.copy()
    return obj.matrix_world.copy()


def flatten_export_matrix(matrix):
    export_matrix = matrix.copy()
    export_matrix.transpose()
    flat_values = []
    for row in export_matrix:
        for value in row:
            flat_values.append(float(value))
    return flat_values


def convert_json_to_fbxex_binary(json_path, binary_path):
    with open(json_path, 'r', encoding='utf-8') as handle:
        raw_data = json.load(handle)

    if "fbxex" in raw_data:
        data = raw_data["fbxex"]
    else:
        data = raw_data

    blob = build_fbxex_binary_blob(data)
    with open(binary_path, 'wb') as handle:
        handle.write(blob)

def convert_to_fbxex_binary(data, binary_path):
    if "fbxex" in data:
        data = data["fbxex"]

    blob = build_fbxex_binary_blob(data)
    with open(binary_path, 'wb') as handle:
        handle.write(blob)


def build_fbxex_binary_blob(data):
    texture_entries = build_texture_entries(data.get("material", {}))
    texture_blob = serialize_texture_entries(texture_entries)

    material_blob = serialize_material_entries(texture_entries)
    node_blob = serialize_node_entries(data.get("node", {}))
    anime_blob = serialize_anime_entries(data.get("anime", {}))

    output = bytearray()
    output.extend(b"fbxex")
    output.extend(b"\x00" * 11)

    output.extend(struct.pack("<I", len(texture_blob)))
    output.extend(struct.pack("<I", len(texture_entries)))
    output.extend(texture_blob)

    output.extend(struct.pack("<I", len(material_blob)))
    output.extend(struct.pack("<I", len(texture_entries)))
    output.extend(material_blob)

    output.extend(struct.pack("<I", len(node_blob)))
    node_count = int(data.get("node", {}).get("count", 0))
    output.extend(struct.pack("<I", node_count))
    output.extend(node_blob)

    output.extend(struct.pack("<I", len(anime_blob)))
    anime_count = int(data.get("anime", {}).get("count", 0))
    output.extend(struct.pack("<I", anime_count))
    output.extend(anime_blob)

    return bytes(output)


def build_texture_entries(material_section):
    count = int(material_section.get("count", 0))
    textures = []
    for index in range(count):
        material = material_section.get(str(index), {})
        filename = material.get("filename", f"texture_{index}.dds")
        textures.append(filename)
    return textures


def serialize_texture_entries(texture_entries):
    blob = bytearray()
    for name in texture_entries:
        blob.extend(pack_fixed_c_string(name, 0x80))
    return bytes(blob)


def serialize_material_entries(texture_entries):
    blob = bytearray()
    for index, name in enumerate(texture_entries):
        blob.extend(pack_fixed_c_string(name, 0x80))
        blob.extend(struct.pack("<I", index))
        blob.extend(struct.pack("<I", index))
        blob.extend(struct.pack("<17f", *([1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0,20.0])))
    return bytes(blob)


def serialize_node_entries(node_section):
    count = int(node_section.get("count", 0))
    blob = bytearray()

    for index in range(count):
        node = node_section.get(str(index), {})
        nodeType = json_index_to_u32(node.get("type", -1))
        child = json_index_to_u32(node.get("child", -1))
        sibling = json_index_to_u32(node.get("sibling", -1))

        has_payload = bool(node.get("vertex")) and bool(node.get("material"))
        node_size = 16
        if has_payload:
            node_size = calculate_node_size(node)

        blob.extend(struct.pack("<I", node_size))
        blob.extend(struct.pack("<I", nodeType))
        blob.extend(struct.pack("<I", child))
        blob.extend(struct.pack("<I", sibling))

        if has_payload:
            blendmode = int(node.get("blendmode", 0))
            alpha = int(node.get("alpha", node.get("dst", 0)))
            matrix_values = ensure_float_list(node.get("matrix", []), 16)
            vertex_values = gather_node_vertices(node)
            material_entries = gather_node_material_entries(node)

            blob.extend(struct.pack("<I", blendmode))
            blob.extend(struct.pack("<I", alpha))
            blob.extend(struct.pack("<16f", *matrix_values))

            blob.extend(struct.pack("<I", len(vertex_values)))
            for vertex in vertex_values:
                blob.extend(struct.pack("<12f", *vertex))

            blob.extend(struct.pack("<I", len(material_entries)))
            for material_index, indices in material_entries:
                blob.extend(struct.pack("<I", material_index))
                blob.extend(struct.pack("<I", len(indices)))
                if indices:
                    blob.extend(struct.pack(f"<{len(indices)}I", *indices))

    return bytes(blob)


def serialize_anime_entries(anime_section):
    count = int(anime_section.get("count", 0))
    blob = bytearray()

    for index in range(count):
        anime_data = anime_section.get(str(index), [0])
        if not anime_data:
            anime_data = [0]

        frame_count = int(anime_data[0])
        matrix_values = ensure_float_list(anime_data[1:], frame_count * 16)

        blob.extend(struct.pack("<I", frame_count))
        if matrix_values:
            blob.extend(struct.pack(f"<{len(matrix_values)}f", *matrix_values))

    return bytes(blob)


def calculate_node_size(node):
    vertex_values = gather_node_vertices(node)
    material_entries = gather_node_material_entries(node)

    size = 16
    size += 8
    size += 16 * 4
    size += 4
    size += len(vertex_values) * 12 * 4
    size += 4
    for _, indices in material_entries:
        size += 8 + len(indices) * 4
    return size


def gather_node_vertices(node):
    vertex_section = node.get("vertex", {})
    vertex_count = int(vertex_section.get("count", 0))
    result = []
    for vertex_index in range(vertex_count):
        packed_vertex = ensure_float_list(vertex_section.get(str(vertex_index), []), 12)
        result.append(packed_vertex)
    return result


def gather_node_material_entries(node):
    material_section = node.get("material", {})
    keys = []
    for key in material_section.keys():
        if key == "count":
            continue
        if str(key).isdigit():
            keys.append(int(key))
    keys.sort()

    result = []
    for key in keys:
        material = material_section.get(str(key), {})
        material_index = int(material.get("index", 0))
        index_count = int(material.get("vertexindexcount", 0))
        indices_raw = material.get("vertexindex", [])
        indices = [int(value) for value in indices_raw[:index_count]]
        if len(indices) < index_count:
            indices.extend([0] * (index_count - len(indices)))
        result.append((material_index, indices))
    return result


def ensure_float_list(values, expected_count):
    result = [float(value) for value in values[:expected_count]]
    if len(result) < expected_count:
        result.extend([0.0] * (expected_count - len(result)))
    return result


def json_index_to_u32(value):
    number = int(value)
    if number < 0:
        return 0xFFFFFFFF
    return number


def pack_fixed_c_string(value, size):
    encoded = str(value).encode('utf-8', errors='ignore')
    encoded = encoded[: max(0, size - 1)]
    return encoded + (b"\x00" * (size - len(encoded)))


def menu_func_import(self, context):
   self.layout.operator(ImportJSON.bl_idname, text="MBTL (.json)")


def menu_func_export(self, context):
   self.layout.operator(ExportBin.bl_idname, text="MBTL (.bin)")


def register():
    from bpy.utils import register_class
    register_class(ImportJSON)
    register_class(ExportBin)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    from bpy.utils import unregister_class
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    unregister_class(ExportBin)
    unregister_class(ImportJSON)

if __name__ == "__main__":
    register()
