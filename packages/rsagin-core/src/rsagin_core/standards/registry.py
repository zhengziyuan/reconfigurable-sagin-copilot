from __future__ import annotations


def standards_registry() -> list[dict]:
    return [
        {
            "id": "3gpp_tr38901",
            "name": "3GPP TR 38.901",
            "role": "Terrestrial 0.5-100 GHz channel reference for L1 path-loss and LOS/NLOS terms.",
            "implemented_scope": "UMa/RMa path-loss subset and deterministic planning LOS/shadow proxies.",
        },
        {
            "id": "3gpp_tr38811",
            "name": "3GPP TR 38.811",
            "role": "NR NTN study reference for satellite/HAPS/UAS link decomposition.",
            "implemented_scope": "Earth-space FSPL plus atmospheric/clutter/shadow planning decomposition.",
        },
        {
            "id": "itu_p676",
            "name": "ITU-R P.676",
            "role": "Atmospheric gaseous attenuation reference.",
            "implemented_scope": "Compact oxygen/water-vapor attenuation approximation for planning.",
        },
        {
            "id": "itu_p838",
            "name": "ITU-R P.838",
            "role": "Rain specific attenuation coefficient reference.",
            "implemented_scope": "ITU-R P.838-3 equations (1)-(5) for k/alpha and specific rain attenuation; effective slant path remains approximate.",
        },
        {
            "id": "itu_y3090",
            "name": "ITU-T Y.3090",
            "role": "Digital twin network requirements and architecture anchor.",
            "implemented_scope": "Observe-estimate-plan-act-evaluate loop represented in platform catalog and reports.",
        },
    ]
