"""
HSAAI Knowledge Genome — v0.6.0

Maps the DNA of enterprise knowledge. Every piece of knowledge has a
genetic code — its origin, mutations, expressions, and heredity.

Like the Human Genome Project mapped human DNA, this maps the
enterprise's knowledge DNA.
"""
from __future__ import annotations
import logging, time, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.genome")

@dataclass
class KnowledgeGene:
    """A gene in the knowledge genome — a fundamental unit of heritable knowledge."""
    gene_id: str = ""
    name: str = ""
    chromosome: str = ""  # knowledge domain (finance, hr, ops, etc.)
    sequence: str = ""  # the core knowledge statement
    expressed_as: list[str] = field(default_factory=list)  # how this manifests
    dominant: bool = True  # does this gene dominate over alternatives?
    mutation_rate: float = 0.0  # how often this knowledge changes
    fitness: float = 0.5  # how valuable this knowledge is
    generation: int = 0  # how many iterations it has survived
    discovered_at: float = 0.0

@dataclass
class KnowledgeMutation:
    """A mutation in a knowledge gene — an update or change."""
    mutation_id: str = ""
    gene_id: str = ""
    old_sequence: str = ""
    new_sequence: str = ""
    mutation_type: str = ""  # refinement, correction, extension, replacement
    fitness_delta: float = 0.0
    timestamp: float = 0.0


class KnowledgeGenomeEngine:
    """
    Maps and manages the enterprise knowledge genome.

    Every piece of enterprise knowledge has a 'genetic code' that
    determines its behavior, evolution, and interaction with other
    knowledge.
    """
    def __init__(self):
        self._genes: dict[str, KnowledgeGene] = {}
        self._mutations: list[KnowledgeMutation] = []
        self._chromosomes: dict[str, list[str]] = defaultdict(list)  # chromosome → gene_ids
        self._gene_counter = 0
        self._mutation_counter = 0

    def discover_gene(self, name: str, chromosome: str, sequence: str,
                      expressed_as: list[str] | None = None) -> KnowledgeGene:
        """Discover a new knowledge gene."""
        self._gene_counter += 1
        gid = f"gene-{self._gene_counter:04d}"
        gene = KnowledgeGene(
            gene_id=gid, name=name, chromosome=chromosome,
            sequence=sequence, expressed_as=expressed_as or [],
            discovered_at=time.time(),
        )
        self._genes[gid] = gene
        self._chromosomes[chromosome].append(gid)
        logger.info("🧬 GENE DISCOVERED: %s on chromosome '%s' — %s", gid, chromosome, sequence[:80])
        return gene

    def mutate(self, gene_id: str, new_sequence: str, mutation_type: str = "refinement") -> KnowledgeMutation:
        """Mutate a knowledge gene — update its sequence."""
        gene = self._genes.get(gene_id)
        if not gene:
            raise ValueError(f"Gene {gene_id} not found")
        self._mutation_counter += 1
        mid = f"mutation-{self._mutation_counter:04d}"
        old = gene.sequence
        gene.sequence = new_sequence
        gene.generation += 1
        if mutation_type == "correction":
            gene.fitness = min(1.0, gene.fitness + 0.1)
        elif mutation_type == "extension":
            gene.fitness = min(1.0, gene.fitness + 0.05)
        mutation = KnowledgeMutation(
            mutation_id=mid, gene_id=gene_id,
            old_sequence=old, new_sequence=new_sequence,
            mutation_type=mutation_type,
            fitness_delta=gene.fitness - 0.5,  # simplified
            timestamp=time.time(),
        )
        self._mutations.append(mutation)
        logger.info("🧬 MUTATION: %s on gene %s (%s) — fitness now: %.2f",
                   mid, gene_id, mutation_type, gene.fitness)
        return mutation

    def get_genome(self, chromosome: str | None = None) -> dict:
        """Get the knowledge genome map."""
        if chromosome:
            gene_ids = self._chromosomes.get(chromosome, [])
            genes = [self._genes[gid] for gid in gene_ids if gid in self._genes]
        else:
            genes = list(self._genes.values())
        return {
            "chromosomes": dict(self._chromosomes),
            "genes": [asdict(g) for g in genes],
            "total_genes": len(genes),
            "total_mutations": len(self._mutations),
        }

    def fittest_genes(self, limit: int = 10) -> list[dict]:
        """Get the fittest knowledge genes."""
        sorted_genes = sorted(self._genes.values(), key=lambda g: g.fitness, reverse=True)
        return [asdict(g) for g in sorted_genes[:limit]]

    def stats(self) -> dict:
        return {
            "total_genes": len(self._genes),
            "total_mutations": len(self._mutations),
            "chromosomes": len(self._chromosomes),
            "avg_fitness": sum(g.fitness for g in self._genes.values()) / max(len(self._genes), 1),
            "oldest_generation": max((g.generation for g in self._genes.values()), default=0),
        }

genome_engine = KnowledgeGenomeEngine()
__all__ = ["KnowledgeGenomeEngine", "KnowledgeGene", "KnowledgeMutation", "genome_engine"]
