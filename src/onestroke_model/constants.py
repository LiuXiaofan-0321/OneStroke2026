"""Shared schema constants.

The old project used five vector channels plus a keypoint channel.  We keep
that order explicit everywhere to avoid hidden channel-order assumptions.
"""

SCHEMA_VERSION = 1
CHANNELS = ("vec1", "vec2", "vec3", "vec4", "vec5", "keypoint")
MASK_FILENAMES = {
    "vec1": "mask_1.npy",
    "vec2": "mask_2.npy",
    "vec3": "mask_3.npy",
    "vec4": "mask_4.npy",
    "vec5": "mask_5.npy",
    "keypoint": "mask_key_point.npy",
}
STACKED_MASK_FILENAME = "0.npy"

