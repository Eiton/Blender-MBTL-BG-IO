#pragma pattern_limit 1800000
#include <type/magic.pat>
#pragma array_limit 200000

struct animeProperty {
    u32 frameCount;
    float matrix[16*frameCount];
};

struct nodeMaterial {
    u32 materialIndex;
    u32 vertexCount;
    u32 vertexIndices[vertexCount];
};

struct vertex {
    float position[3];
    float normal[3];
    float color[4];
    float uv[2];
};

struct nodeProperty {
    u32 nodeSize;
    u32 nodeType;
    u32 childIndex;
    u32 siblingIndex;
    if(nodeSize>16){
        u32 blendmode;
        u32 alpha;
        float matrix[16];
        u32 vertexCount;
        vertex vertices[vertexCount];
        u32 materialCount;
        nodeMaterial m[materialCount];
    }
};

struct materialProperty {
    char textureName[0x80];
    u32 materialIndex;
    u32 textureIndex;
    float params[17];
};

struct textureProperty {
    char textureName[0x80];
};

struct header {
    type::Magic<"fbxex"> fbex;
    padding[11];
};

struct file {
    header h;
    // Size in byte
    u32 texturePropertySize;
    u32 textureCount;
    textureProperty textures[textureCount];
    u32 materialPropertySize;
    u32 materialCount;
    materialProperty materials[materialCount];
    u32 nodePropertySize;
    u32 nodeCount;
    nodeProperty nodes[nodeCount];
    u32 animePropertySize;
    u32 animeCount;
    animeProperty animes[animeCount];
};
file f @ 0;