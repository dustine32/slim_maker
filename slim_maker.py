from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.io.ontol_renderers import GraphRenderer, OboFormatGraphRenderer
from ontobio.io.gafparser import GafParser
import argparse
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--usage_count_constraint')
parser.add_argument('-g', '--gaf_file')
parser.add_argument('-o', '--outfile')
parser.add_argument('-u', '--use_cache', action='store_const', const=True)
parser.add_argument('-w', '--ontology_file')

USAGE_COUNT_CONSTRAINT = 5
ONLY_SHARED_ANCESTORS = True
RELATIONS = ["subClassOf","BFO:0000050"]
GAF_FILE = "/Users/ebertdu/Downloads/ancestor_node_association.paint.gaf"
OUTFILE = "panther_slim_shared.obo"


def dump_to_json(filename, terms):
    with open(filename, "w+") as f:
        f.write(json.dumps(terms))

def get_from_json(json_file):
    with open(json_file) as f:
        terms = json.loads(f.read())
        print("File '{}' used to load term count dictionary - {} keys loaded".format(json_file, len(terms)))
        return terms

def term_usage_count(term, associations):
    usage_count = 0
    for a in associations:
        if a["object"]["id"] == term:
            usage_count += 1
    return usage_count

def get_common_terms(ontology, gaf_file, usage_count_constraint=5, regen_cache=True):
    terms = {}
    tmp_terms_fname = "/tmp/{}.json".format(os.path.basename(gaf_file))
    assocs = GafParser().parse(gaf_file, skipheader=True)
    if not regen_cache and os.path.isfile(tmp_terms_fname):
        terms = get_from_json(tmp_terms_fname)
    else:
        for a in assocs:
            ## These counts will be overwritten, just initializing term keys at this point
            if a["object"]["id"] not in terms:
                terms[a["object"]["id"]] = 1
            else:
                terms[a["object"]["id"]] += 1
        cached_counts = {}
        prog_counter = 0
        print("{} terms to go through".format(len(terms)))
        for t in terms:
            prog_counter += 1
            # print("Currently on {}".format(prog_counter))
            if t in cached_counts:
                t_count = cached_counts[t]
            else:
                t_count = term_usage_count(t, assocs)
                cached_counts[t] = t_count
            desc_terms = ontology.subontology(ontology.descendants(t), relations=RELATIONS).nodes()
            for dt in desc_terms:
                if dt in cached_counts:
                    d_count = cached_counts[dt]
                else:
                    d_count = term_usage_count(dt, assocs)
                    cached_counts[dt] = d_count
                t_count += d_count
            terms[t] = t_count
        # Cache terms
        dump_to_json(tmp_terms_fname, terms)

    common_terms = {}
    for t in terms:
        if terms[t] >= usage_count_constraint:
            common_terms[t] = terms[t]
    return common_terms

def fill_in_relations(subontology, ontology_orig):
    for term in subontology.nodes():
        for ancestor in subontology.nodes():
            if term == ancestor:
                continue
            sub_ancestors = subontology.subontology(subontology.ancestors(term) + [term])
            orig_ancestors = ontology_orig.subontology(ontology_orig.ancestors(term) + [term])
            # print("sub_ancestors:", sub_ancestors.nodes())
            # print("orig_ancestors:", orig_ancestors.nodes())
            for rel in ['subClassOf','BFO:0000050']:
                rel_sub_ancestors = sub_ancestors.ancestors(term, relations=[rel])
                rel_orig_ancestors = orig_ancestors.ancestors(term, relations=[rel])
                if ancestor not in rel_sub_ancestors and ancestor in rel_orig_ancestors:
                    subontology.graph.add_edge(ancestor, term, pred=rel)
    return subontology
            # if (term, ancestor) not in subontology.edges():
            #     for
                # Look for edges in original ontology
                # if t1 in ontology_orig.ancestors(t2, relations=['subClassOf']):
                #   subontology.add_edge(t1, t2, 'subClassOf')

                # new_edges = get_edges(orig_ont_edges, [])
                # for k2 in orig_ont_edges[t1]:
                #     for r in orig_ont_edges[t1][k2]:
                #         pred = r['pred']
                #         if pred == "subClassOf" or pred == "BFO:0000050":
                #             return


if __name__ == "__main__":
    args = parser.parse_args()

    USAGE_COUNT_CONSTRAINT = int(args.usage_count_constraint)
    GAF_FILE = args.gaf_file
    OUTFILE = args.outfile
    regen_cache = None
    if args.use_cache:
        regen_cache = False

    # ont = OntologyFactory().create("/Users/ebertdu/Downloads/go.owl")
    ont = OntologyFactory().create(args.ontology_file)
    # aset = AssociationSetFactory().create(ont, file=GAF_FILE)
    common_terms = get_common_terms(ont, GAF_FILE, USAGE_COUNT_CONSTRAINT, regen_cache)
    print("Grabbed {} common terms".format(len(common_terms)))

    all_terms = []
    term_to_ancestors = {}
    for t in common_terms:
        subont = ont.subontology(ont.ancestors(t), relations=RELATIONS)
        term_to_ancestors[t] = subont.nodes()  # Keep ancestor list in case we want to only include common ancestors
        for n in subont.nodes():
            if n not in all_terms:
                all_terms.append(n)
    print("Grabbed all ancestors")

    if ONLY_SHARED_ANCESTORS:
        shared_ancestors = []
        for t in common_terms:
            for anc in term_to_ancestors[t]:
                ## x-y term matrix checking for shared ancestors in multiple ancestor sets
                for other_t in common_terms:
                    if other_t == t:
                        continue
                    else:
                        if anc in term_to_ancestors[other_t]:
                            shared_ancestors.append(anc)
        all_terms = set(shared_ancestors + list(common_terms.keys()))
        print("Filtered for shared ancestors only")

    print("{} terms included in panther_slim".format(len(all_terms)))
    hierarchy_ont = ont.subontology(all_terms, relations=RELATIONS)
    # hierarchy_ont = fill_in_relations(hierarchy_ont, ont)
    renderer = GraphRenderer.create("obo")
    renderer.outfile = OUTFILE
    renderer.write(hierarchy_ont)