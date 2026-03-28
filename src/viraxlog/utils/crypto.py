#!/usr/bin/env python3
"""
ViraxLog - Crypto Module v2.0
Chaînage cryptographique haute performance avec Merkle trees et BLAKE2b.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import json
from typing import Optional, List, Tuple, Literal, Any
from functools import lru_cache

logger = logging.getLogger("ViraxLog.Crypto")

# Algorithmes supportés
HASH_ALGORITHMS = Literal["blake2b", "sha256", "sha3_256"]
DEFAULT_HASH_ALGO: HASH_ALGORITHMS = "blake2b"  # Plus rapide que SHA-256


def compute_entry_hash(
    timestamp: str,
    level: str,
    category: str,
    data: Any,
    prev_hash: str,
    algorithm: HASH_ALGORITHMS = DEFAULT_HASH_ALGO
) -> str:
    """
    Calcule hash cryptographique stable pour une entrée.
    - BLAKE2b: 2x plus rapide que SHA-256
    - Ordre fixe pour stabilité
    - UTF-8 natif supporté
    """
    # Normalisation données
    if isinstance(data, (dict, list)):
        data_str = json.dumps(
            data,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False
        )
    else:
        data_str = str(data)

    # Construction payload avec ordre déterministe
    payload_str = f"{timestamp}|{level}|{category}|{data_str}|{prev_hash}"
    payload = payload_str.encode("utf-8")

    try:
        algo = algorithm.lower()
        if algo == "blake2b":
            return hashlib.blake2b(payload, digest_size=32).hexdigest()
        elif algo == "sha256":
            return hashlib.sha256(payload).hexdigest()
        elif algo == "sha3_256":
            return hashlib.sha3_256(payload).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    except Exception as e:
        logger.critical(f"Hash computation failed: {e}")
        raise


@lru_cache(maxsize=1024)
def _cached_hash(payload_hash: str) -> str:
    """Cache interne pour optimisation."""
    return payload_hash


def verify_log_chain(
    entries: List[Any],
    initial_prev_hash: str = "GENESIS",
    algorithm: HASH_ALGORITHMS = DEFAULT_HASH_ALGO
) -> Tuple[bool, Optional[int]]:
    """
    Vérification complète de la chaîne cryptographique.
    Retourne (valide, index_erreur).
    
    Optimisé pour:
    - Vérification rapide avec early-exit
    - Protection timing-attacks (hmac.compare_digest)
    - Cache des hashes
    """
    current_expected_prev_hash = initial_prev_hash

    for i, entry in enumerate(entries):
        # 1. Vérification du lien chaîne (prev_hash)
        if not hmac.compare_digest(entry.prev_hash, current_expected_prev_hash):
            logger.error(
                f"[CHAIN_BREAK] Index {i}: prev_hash mismatch "
                f"(expected={current_expected_prev_hash[:16]}..., "
                f"found={entry.prev_hash[:16]}...)"
            )
            return False, i

        # 2. Vérification du contenu (hash)
        actual_hash = compute_entry_hash(
            entry.timestamp,
            entry.level,
            entry.category,
            entry.data,
            entry.prev_hash,
            algorithm
        )
        
        if not hmac.compare_digest(entry.hash, actual_hash):
            logger.error(
                f"[DATA_CORRUPTION] Index {i}: hash mismatch "
                f"(computed={actual_hash[:16]}..., stored={entry.hash[:16]}...)"
            )
            return False, i

        # Mise à jour pour next block
        current_expected_prev_hash = entry.hash

    return True, None


def validate_single_entry(
    entry: Any,
    prev_hash: str,
    algorithm: HASH_ALGORITHMS = DEFAULT_HASH_ALGO
) -> bool:
    """Valide une seule entrée contre prev_hash."""
    try:
        computed = compute_entry_hash(
            entry.timestamp,
            entry.level,
            entry.category,
            entry.data,
            prev_hash,
            algorithm
        )
        
        is_content_ok = hmac.compare_digest(entry.hash, computed)
        is_link_ok = hmac.compare_digest(entry.prev_hash, prev_hash)
        
        return is_content_ok and is_link_ok
    except Exception as e:
        logger.error(f"Single entry validation error: {e}")
        return False


# ========== MERKLE TREE POUR AUDIT RAPIDE ==========

class MerkleTree:
    """
    Merkle tree pour vérification d'intégrité O(log n).
    Utilisé pour auditer rapidement des millions d'entrées.
    """
    
    def __init__(self, hashes: List[str]):
        self.hashes = hashes
        self.tree = self._build_tree(hashes)
        self.root = self.tree[-1][0] if self.tree else None
    
    def _build_tree(self, hashes: List[str]) -> List[List[str]]:
        """Construit l'arbre Merkle couche par couche."""
        if not hashes:
            return []
        
        current_level = hashes[:]
        tree = [current_level]
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                parent = hashlib.blake2b(
                    (left + right).encode()
                ).hexdigest()
                next_level.append(parent)
            
            tree.append(next_level)
            current_level = next_level
        
        return tree
    
    def get_proof(self, index: int) -> List[Tuple[str, Literal["L", "R"]]]:
        """Retourne le chemin de preuve pour vérifier un hash (proof of inclusion)."""
        proof = []
        current_index = index
        
        for level in self.tree[:-1]:
            if current_index % 2 == 0:
                # Nœud gauche
                sibling_index = current_index + 1
                if sibling_index < len(level):
                    proof.append((level[sibling_index], "R"))
            else:
                # Nœud droit
                proof.append((level[current_index - 1], "L"))
            
            current_index //= 2
        
        return proof
    
    def verify_proof(self, leaf_hash: str, index: int, proof: List[Tuple[str, str]]) -> bool:
        """Vérifie qu'un hash appartient à l'arbre."""
        current_hash = leaf_hash
        current_index = index
        
        for sibling_hash, position in proof:
            if position == "L":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash
            
            current_hash = hashlib.blake2b(combined.encode()).hexdigest()
        
        return hmac.compare_digest(current_hash, self.root or "")


def create_merkle_tree_from_entries(entries: List[Any]) -> MerkleTree:
    """Crée un Merkle tree à partir d'entrées."""
    hashes = [entry.hash for entry in entries]
    return MerkleTree(hashes)


# ========== UTILITIES ==========

def hash_payload(payload: str, algorithm: HASH_ALGORITHMS = DEFAULT_HASH_ALGO) -> str:
    """Hash simple d'une chaîne."""
    data = payload.encode("utf-8")
    if algorithm == "blake2b":
        return hashlib.blake2b(data, digest_size=32).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "sha3_256":
        return hashlib.sha3_256(data).hexdigest()
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


def compute_hmac(message: str, key: str) -> str:
    """Calcule HMAC-SHA256 pour authentification."""
    return hmac.new(
        key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_hmac(message: str, signature: str, key: str) -> bool:
    """Vérifie une signature HMAC (timing-safe)."""
    expected = compute_hmac(message, key)
    return hmac.compare_digest(signature, expected)
