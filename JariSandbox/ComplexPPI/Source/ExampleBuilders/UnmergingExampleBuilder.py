"""
Edge Examples
"""
__version__ = "$Revision: 1.7 $"

import sys, os
thisPath = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(thisPath,"..")))
from Core.ExampleBuilder import ExampleBuilder
import Core.ExampleBuilder
from Core.IdSet import IdSet
import Core.ExampleUtils as ExampleUtils
from FeatureBuilders.MultiEdgeFeatureBuilder import MultiEdgeFeatureBuilder
from FeatureBuilders.TriggerFeatureBuilder import TriggerFeatureBuilder
from FeatureBuilders.TokenFeatureBuilder import TokenFeatureBuilder
from FeatureBuilders.BioInferOntologyFeatureBuilder import BioInferOntologyFeatureBuilder
from FeatureBuilders.NodalidaFeatureBuilder import NodalidaFeatureBuilder
import Graph.networkx_v10rc1 as NX10
from Utils.ProgressCounter import ProgressCounter
#IF LOCAL
import Utils.BioInfer.OntologyUtils as OntologyUtils
#ENDIF
import combine
import cElementTreeUtils as ETUtils

def combinations(iterable, r):
    # combinations('ABCD', 2) --> AB AC AD BC BD CD
    # combinations(range(4), 3) --> 012 013 023 123
    pool = tuple(iterable)
    n = len(pool)
    if r > n:
        return
    indices = range(r)
    yield tuple(pool[i] for i in indices)
    while True:
        for i in reversed(range(r)):
            if indices[i] != i + n - r:
                break
        else:
            return
        indices[i] += 1
        for j in range(i+1, r):
            indices[j] = indices[j-1] + 1
        yield tuple(pool[i] for i in indices)

def compareInteractionPrecedence(e1, e2):
    """
    e1/e2 = (interaction, pathdist, lindist, tok2pos)
    """
    if e1[1] > e2[1]:
        return 1
    elif e1[1] < e2[1]:
        return -1
    else: # same dependency distance
        if e1[2] > e2[2]:
            return 1
        elif e1[2] < e2[2]:
            return -1
        else: # same linear distance
            if e1[3] > e2[3]:
                return 1
            elif e1[3] < e2[3]:
                return -1
            else: # same head token for entity 2
                return 0
                #assert False, ("Precedence error",e1,e2)

class UnmergingExampleBuilder(ExampleBuilder):
    """
    This example builder makes edge examples, i.e. examples describing
    the event arguments.
    """
    def __init__(self, style=["typed","directed","headsOnly"], length=None, types=[], featureSet=None, classSet=None):
        if featureSet == None:
            featureSet = IdSet()
        if classSet == None:
            classSet = IdSet(1)
        else:
            classSet = classSet
        assert( classSet.getId("neg") == 1 )
        
        ExampleBuilder.__init__(self, classSet=classSet, featureSet=featureSet)
        self.styles = style
        
        self.styles = ["trigger_features","typed","directed","no_linear","entities","genia_limits","noMasking","maxFeatures"]
        self.multiEdgeFeatureBuilder = MultiEdgeFeatureBuilder(self.featureSet)
        if "graph_kernel" in self.styles:
            from FeatureBuilders.GraphKernelFeatureBuilder import GraphKernelFeatureBuilder
            self.graphKernelFeatureBuilder = GraphKernelFeatureBuilder(self.featureSet)
        if "noAnnType" in self.styles:
            self.multiEdgeFeatureBuilder.noAnnType = True
        if "noMasking" in self.styles:
            self.multiEdgeFeatureBuilder.maskNamedEntities = False
        if "maxFeatures" in self.styles:
            self.multiEdgeFeatureBuilder.maximum = True
        self.tokenFeatureBuilder = TokenFeatureBuilder(self.featureSet)
        if "ontology" in self.styles:
            self.multiEdgeFeatureBuilder.ontologyFeatureBuilder = BioInferOntologyFeatureBuilder(self.featureSet)
        if "nodalida" in self.styles:
            self.nodalidaFeatureBuilder = NodalidaFeatureBuilder(self.featureSet)
        #IF LOCAL
        if "bioinfer_limits" in self.styles:
            self.bioinferOntologies = OntologyUtils.getBioInferTempOntology()
            #self.bioinferOntologies = OntologyUtils.loadOntologies(OntologyUtils.g_bioInferFileName)
        #ENDIF
        self.pathLengths = length
        assert(self.pathLengths == None)
        self.types = types
        if "random" in self.styles:
            from FeatureBuilders.RandomFeatureBuilder import RandomFeatureBuilder
            self.randomFeatureBuilder = RandomFeatureBuilder(self.featureSet)

        self.triggerFeatureBuilder = TriggerFeatureBuilder(self.featureSet)
        
        #self.outFile = open("exampleTempFile.txt","wt")

    @classmethod
    def run(cls, input, gold, output, parse, tokenization, style, idFileTag=None, append=False):
        """
        An interface for running the example builder without needing to create a class
        """
        classSet, featureSet = cls.getIdSets(idFileTag)
        if style != None:
            e = UnmergingExampleBuilder(style=style, classSet=classSet, featureSet=featureSet)
        else:
            e = UnmergingExampleBuilder(classSet=classSet, featureSet=featureSet)
        sentences = cls.getSentences(input, parse, tokenization)
        if gold != None:
            goldSentences = cls.getSentences(gold, parse, tokenization)
        else:
            goldSentences = None
        e.buildExamplesForSentences(sentences, goldSentences, output, idFileTag, append=append)
    
    def getInteractionEdgeLengths(self, sentenceGraph, paths):
        """
        Return dependency and linear length of all interaction edges
        (measured between the two tokens).
        """
        interactionLengths = {}
        for interaction in sentenceGraph.interactions:
            # Calculated interaction edge dep and lin length
            e1 = sentenceGraph.entitiesById[interaction.get("e1")]
            e2 = sentenceGraph.entitiesById[interaction.get("e2")]
            t1 = sentenceGraph.entityHeadTokenByEntity[e1]
            t2 = sentenceGraph.entityHeadTokenByEntity[e2]
            # Get dep path length
            if t1 != t2 and paths.has_key(t1) and paths[t1].has_key(t2):
                pathLength = len(paths[t1][t2])
            else: # no dependencyPath
                pathLength = 999999 # more than any real path
            # Linear distance
            t1Pos = -1
            t2Pos = -1
            for i in range(len(sentenceGraph.tokens)):
                if sentenceGraph.tokens[i] == t1:
                    t1Pos = i
                    if t2Pos != -1:
                        break
                if sentenceGraph.tokens[i] == t2:
                    t2Pos = i
                    if t1Pos != -1:
                        break
            linLength = abs(t1Pos - t2Pos)
            interactionLengths[interaction] = (interaction, pathLength, linLength, t2Pos)
        return interactionLengths

    def buildExamplesForSentences(self, sentences, goldSentences, output, idFileTag=None, append=False):            
        examples = []
        counter = ProgressCounter(len(sentences), "Build examples")
        
        if append:
            outfile = open(output, "at")
        else:
            outfile = open(output, "wt")
        exampleCount = 0
        for i in range(len(sentences)):
            sentence = sentences[i]
            goldSentence = [None]
            if goldSentences != None:
                goldSentence = goldSentences[i]
            counter.update(1, "Building examples ("+sentence[0].getSentenceId()+"): ")
            examples = self.buildExamples(sentence[0], goldSentence[0], append=append)
            exampleCount += len(examples)
            examples = self.preProcessExamples(examples)
            ExampleUtils.appendExamples(examples, outfile)
        outfile.close()
    
        print >> sys.stderr, "Examples built:", exampleCount
        print >> sys.stderr, "Features:", len(self.featureSet.getNames())
        #IF LOCAL
        if self.exampleStats.getExampleCount() > 0:
            self.exampleStats.printStats()
        #ENDIF
        # Save Ids
        if idFileTag != None: 
            print >> sys.stderr, "Saving class names to", idFileTag + ".class_names"
            self.classSet.write(idFileTag + ".class_names")
            print >> sys.stderr, "Saving feature names to", idFileTag + ".feature_names"
            self.featureSet.write(idFileTag + ".feature_names")

    
    def definePredictedValueRange(self, sentences, elementName):
        self.multiEdgeFeatureBuilder.definePredictedValueRange(sentences, elementName)                        
    
    def getPredictedValueRange(self):
        return self.multiEdgeFeatureBuilder.predictedRange
    
    def filterEdgesByType(self, edges, typesToInclude):
        if len(typesToInclude) == 0:
            return edges
        edgesToKeep = []
        for edge in edges:
            if edge.get("type") in typesToInclude:
                edgesToKeep.append(edge)
        return edgesToKeep
    
    def getCategoryNameFromTokens(self, sentenceGraph, t1, t2, directed=True):
        """
        Example class. Multiple overlapping edges create a merged type.
        """
        types = set()
        if sentenceGraph.interactionGraph.has_edge(t1, t2):
            intEdges = sentenceGraph.interactionGraph.get_edge_data(t1, t2, default={})
            # NOTE: Only works if keys are ordered integers
            for i in range(len(intEdges)):
                types.add(intEdges[i]["element"].get("type"))
        if (not directed) and sentenceGraph.interactionGraph.has_edge(t2, t1):
            intEdges = sentenceGraph.interactionGraph.get_edge(t2, t1, default={})
            # NOTE: Only works if keys are ordered integers
            for i in range(len(intEdges)):
                types.add(intEdges[i]["element"].get("type"))
        types = list(types)
        types.sort()
        categoryName = ""
        for name in types:
            if categoryName != "":
                categoryName += "---"
            categoryName += name
        if categoryName != "":
            return categoryName
        else:
            return "neg"
        
    def getCategoryName(self, sentenceGraph, e1, e2, directed=True):
        """
        Example class. Multiple overlapping edges create a merged type.
        """
        interactions = sentenceGraph.getInteractions(e1, e2)
        if not directed:
            interactions.extend(sentenceGraph.getInteractions(e2, e1))
        
        types = set()
        for interaction in interactions:
            types.add(interaction.attrib["type"])
        types = list(types)
        types.sort()
        categoryName = ""
        for name in types:
            if categoryName != "":
                categoryName += "---"
            categoryName += name
        if categoryName != "":
            return categoryName
        else:
            return "neg"           
    
    def preProcessExamples(self, allExamples):
        # Duplicates cannot be removed here, as they should only be removed from the training set. This is done
        # in the classifier.
#        if "no_duplicates" in self.styles:
#            count = len(allExamples)
#            print >> sys.stderr, " Removing duplicates,", 
#            allExamples = ExampleUtils.removeDuplicates(allExamples)
#            print >> sys.stderr, "removed", count - len(allExamples)
        if "normalize" in self.styles:
            print >> sys.stderr, " Normalizing feature vectors"
            ExampleUtils.normalizeFeatureVectors(allExamples)
        return allExamples   
    
    def isPotentialGeniaInteraction(self, e1, e2):
        """
        Genia named entities can never act as event triggers, so
        edges can't leave from them. We can reduce the number of 
        examples generated by removing these always negative cases.
        """
        if e1.get("isName") == "True" and e2.get("isName") == "True":
            return False
        elif e1.get("isName") == "True" and e2.get("isName") == "False":
            return False
        else:
            return True
    
    def nxMultiDiGraphToUndirected(self, graph):
        undirected = NX10.MultiGraph(name=graph.name)
        undirected.add_nodes_from(graph)
        undirected.add_edges_from(graph.edges_iter())
        return undirected
    
    def eventIsGold(self, entity, arguments, sentenceGraph, goldGraph, goldEntitiesByOffset):
        offset = entity.get("headOffset")
        if not goldEntitiesByOffset.has_key(offset):
            return False
        eType = entity.get("type")
        goldEntities = goldEntitiesByOffset[offset]
        
        for goldEntity in goldEntities:
            isGold = True
            
            if goldEntity.get("type") != eType:
                isGold = False
                continue
            goldEntityId = goldEntity.get("id")
            
            goldInteractions = []
            for goldInteraction in goldGraph.interactions:
                if goldInteraction.get("e1") == goldEntityId:
                    goldInteractions.append(goldInteraction)
            
            # Argument count rules
            if len(goldInteractions) != len(arguments):
                isGold = False
                continue
            argTypeCounts = {}
            for argument in arguments:
                argType = argument.get("type")
                if not argTypeCounts.has_key(argType): argTypeCounts[argType] = 0
                argTypeCounts[argType] += 1
            goldTypeCounts = {}
            for argument in goldInteractions:
                argType = argument.get("type")
                if not goldTypeCounts.has_key(argType): goldTypeCounts[argType] = 0
                goldTypeCounts[argType] += 1
            if argTypeCounts != goldTypeCounts:
                isGold = False
                continue
            
            # Exact argument matching
            for argument in arguments:
                e1 = argument.get("e1")
                e2 = argument.get("e2")
                e2Entity = sentenceGraph.entitiesById[e2]
                e2Offset = e2Entity.get("headOffset")
                e2Type = e2Entity.get("type")
                argType = argument.get("type")
                
                found = False
                for goldInteraction in goldInteractions:
                    if goldInteraction.get("type") == argType:
                        goldE2Entity = goldGraph.entitiesById[goldInteraction.get("e2")] 
                        if goldE2Entity.get("headOffset") == e2Offset and goldE2Entity.get("type") == e2Type:
                            found = True
                            break
                if found == False:
                    isGold = False
                    break

            # Event is in gold
            if isGold:
                break
        
        return isGold
    
    def getArgumentCombinations(self, eType, interactions):
        combs = []
        if eType == "Binding":
            # Making examples for only all-together/all-separate cases
            # doesn't work, since even gold data has several cases of
            # overlapping bindings with different numbers of arguments
            #if len(interactions) > 0:
            #    return [interactions]
            #else:
            #    return interactions
            
            # Skip causes
            themes = []
            for interaction in interactions:
                if interaction.get("type") == "Theme":
                    themes.append(interaction)
                
            for i in range(len(themes)):
                for j in combinations(themes, i+1):
                    combs.append(j)
            return combs
        else: # one of the regulation-types, or one of the simple types
            themes = []
            causes = []
            for interaction in interactions:
                iType = interaction.get("type")
                #assert iType in ["Theme", "Cause"], (iType, ETUtils.toStr(interaction))
                if iType not in ["Theme", "Cause"]:
                    continue
                if iType == "Theme":
                    themes.append(interaction)
                else:
                    causes.append(interaction)
            if eType.find("egulation") == -1: # Only regulations can have causes
                causes = []
            themeAloneCombinations = []
            for theme in themes:
                themeAloneCombinations.append([theme])
            #print "Combine", combine.combine(themes, causes), "TA", themeAloneCombinations
            return combine.combine(themes, causes) + themeAloneCombinations
            
    def buildExamples(self, sentenceGraph, goldGraph, append=False):
        """
        Build examples for a single sentence. Returns a list of examples.
        See Core/ExampleUtils for example format.
        """
        self.multiEdgeFeatureBuilder.setFeatureVector(resetCache=True)
        self.triggerFeatureBuilder.initSentence(sentenceGraph)
        
        examples = []
        exampleIndex = 0
        if append == True:
            exampleIndex += 1000
        
        undirected = self.nxMultiDiGraphToUndirected(sentenceGraph.dependencyGraph)
        paths = NX10.all_pairs_shortest_path(undirected, cutoff=999)
        
        # Get argument order
        self.interactionLenghts = self.getInteractionEdgeLengths(sentenceGraph, paths)
        
        # Map tokens to entities
        tokenByOffset = {}
        for i in range(len(sentenceGraph.tokens)):
            token = sentenceGraph.tokens[i]
            if goldGraph != None:
                goldToken = goldGraph.tokens[i]
                assert token.get("id") == goldToken.get("id") and token.get("charOffset") == goldToken.get("charOffset")
            tokenByOffset[token.get("charOffset")] = token.get("id")
        
        # Map gold entities to their head offsets
        goldEntitiesByOffset = {}
        if goldGraph != None:
            for entity in goldGraph.entities:
                offset = entity.get("headOffset")
                assert offset != None
                if not goldEntitiesByOffset.has_key(offset):
                    goldEntitiesByOffset[offset] = []
                goldEntitiesByOffset[offset].append(entity)
        
        # Generate examples based on interactions between entities or interactions between tokens
        interactionsByEntityId = {}
        for entity in sentenceGraph.entities:
            interactionsByEntityId[entity.get("id")] = []
        for interaction in sentenceGraph.interactions:
            if interaction.get("type") == "neg":
                continue
            e1Id = interaction.get("e1")
            interactionsByEntityId[e1Id].append(interaction)
        
        exampleIndex = 0
        for entity in sentenceGraph.entities:
            eType = entity.get("type")
            #if eType not in ["Binding", "Positive_regulation", "Negative_regulation", "Regulation"]:
            #    continue
            
            #if not goldEntitiesByOffset.has_key(entity.get("headOffset")):
            #    continue
            
            interactions = interactionsByEntityId[entity.get("id")]
            argCombinations = self.getArgumentCombinations(eType, interactions)
            #if len(argCombinations) <= 1:
            #    continue
            for argCombination in argCombinations:
                assert len(argCombination) > 0, eType + ": " + str(argCombinations)
                # Originally binary classification
                if goldGraph != None:
                    isGoldEvent = self.eventIsGold(entity, argCombination, sentenceGraph, goldGraph, goldEntitiesByOffset)
                    #if eType == "Binding":
                    #    print argCombination[0].get("e1"), len(argCombination), isGoldEvent
                else:
                    isGoldEvent = False
                # Named (multi-)class
                if isGoldEvent:
                    #category = "event"
                    category = eType
                    if category.find("egulation") != -1:
                        category = "All_regulation"
                    elif category != "Binding":
                        category = "simple6"
                else:
                    category = "neg"
                    
                features = {}
                
                argString = ""
                for arg in argCombination:
                    argString += "," + arg.get("id")
                extra = {"xtype":"um","e":entity.get("id"),"i":argString[1:],"etype":entity.get("type"),"class":category}
                
                self.exampleStats.addExample(category)
                example = self.buildExample(sentenceGraph, paths, entity, argCombination, interactions)
                example[0] = sentenceGraph.getSentenceId()+".x"+str(exampleIndex)
                example[1] = self.classSet.getId(category)
                example[3] = extra
                examples.append( example )
                exampleIndex += 1
            
        return examples
    
    def buildExample(self, sentenceGraph, paths, eventEntity, argCombination, allInteractions): #themeEntities, causeEntities=None):
        # NOTE!!!! TODO
        # add also features for arguments present, but not in this combination
        
        features = {}
        self.features = features
        
        self.buildInterArgumentBagOfWords(argCombination, sentenceGraph)
        
        eventEntityType = eventEntity.get("type")
        if eventEntityType == "Binding":
            interactionIndex = {}
            groupInteractionLengths = []
            for interaction in allInteractions:
                groupInteractionLengths.append(self.interactionLenghts[interaction])
            groupInteractionLengths.sort(compareInteractionPrecedence)
            #print groupInteractionLengths
            for i in range(len(groupInteractionLengths)):
                interactionIndex[groupInteractionLengths[i][0]] = i
        
        eventToken = sentenceGraph.entityHeadTokenByEntity[eventEntity]
        self.triggerFeatureBuilder.setFeatureVector(self.features)
        self.triggerFeatureBuilder.tag = "trg_"
        self.triggerFeatureBuilder.buildFeatures(eventToken)
        self.triggerFeatureBuilder.tag = None
        
        #self.setFeature("rootType_"+eventEntity.get("type"), 1)
        
        argThemeCount = 0
        argCauseCount = 0
        # Current example's edge combination
        for arg in argCombination:
            if arg.get("type") == "Theme":
                argThemeCount += 1
                tag = "argTheme"
                self.buildArgumentFeatures(sentenceGraph, paths, features, eventToken, arg, tag)
                if eventEntityType == "Binding":
                    tag += str(interactionIndex[arg])
                    self.buildArgumentFeatures(sentenceGraph, paths, features, eventToken, arg, tag)
            else: # Cause
                argCauseCount += 1
                self.buildArgumentFeatures(sentenceGraph, paths, features, eventToken, arg, "argCause")
        
        # Edge group context
        contextThemeCount = 0
        contextCauseCount = 0
        for interaction in allInteractions:
            if interaction in argCombination: # Already part of current example's combination
                continue
            if interaction.get("type") == "Theme":
                contextThemeCount += 1
                tag = "conTheme"
                self.buildArgumentFeatures(sentenceGraph, paths, features, eventToken, interaction, tag)
                if eventEntityType == "Binding":
                    tag += str(interactionIndex[interaction])
                    self.buildArgumentFeatures(sentenceGraph, paths, features, eventToken, interaction, tag)
            else: # Cause
                contextCauseCount += 1
                self.buildArgumentFeatures(sentenceGraph, paths, features, eventToken, interaction, "conCause")
        
        self.setFeature("argCount", len(argCombination))
        self.setFeature("argCount_" + str(len(argCombination)), 1)
        self.setFeature("interactionCount", len(allInteractions))
        self.setFeature("interactionCount_" + str(len(allInteractions)), 1)
        
        self.setFeature("argThemeCount", argThemeCount)
        self.setFeature("argThemeCount_" + str(argThemeCount), 1)
        self.setFeature("argCauseCount", argCauseCount)
        self.setFeature("argCauseCount_" + str(argCauseCount), 1)

        self.setFeature("interactionThemeCount", contextThemeCount)
        self.setFeature("interactionThemeCount_" + str(contextThemeCount), 1)
        self.setFeature("interactionCauseCount", contextCauseCount)
        self.setFeature("interactionCauseCount_" + str(contextCauseCount), 1)        
        
        self.triggerFeatureBuilder.tag = ""
        self.triggerFeatureBuilder.setFeatureVector(None)
        
        # Common features
#        if e1Type.find("egulation") != -1: # leave r out to avoid problems with capitalization
#            if entity2.get("isName") == "True":
#                features[self.featureSet.getId("GENIA_regulation_of_protein")] = 1
#            else:
#                features[self.featureSet.getId("GENIA_regulation_of_event")] = 1

        # define extra attributes
        return [None,None,features,None]

    def buildArgumentFeatures(self, sentenceGraph, paths, features, eventToken, arg, tag):
        argEntity = sentenceGraph.entitiesById[arg.get("e2")]
        argToken = sentenceGraph.entityHeadTokenByEntity[argEntity]
        self.buildEdgeFeatures(sentenceGraph, paths, features, eventToken, argToken, tag)
        self.triggerFeatureBuilder.tag = tag + "trg_"
        self.triggerFeatureBuilder.buildFeatures(argToken)
        if argEntity.get("isName") == "True":
            self.setFeature(tag+"Protein", 1)
        else:
            self.setFeature(tag+"Event", 1)
            self.setFeature("nestingEvent", 1)
        self.setFeature(tag+"_"+argEntity.get("type"), 1)
    
    def buildEdgeFeatures(self, sentenceGraph, paths, features, eventToken, argToken, tag):
        #eventToken = sentenceGraph.entityHeadTokenByEntity[eventNode]
        #argToken = sentenceGraph.entityHeadTokenByEntity[argNode]
        self.multiEdgeFeatureBuilder.tag = tag + "_"
        self.multiEdgeFeatureBuilder.setFeatureVector(features, None, None, False)
        
        self.setFeature(tag+"_present", 1)
        
        if eventToken != argToken and paths.has_key(eventToken) and paths[eventToken].has_key(argToken):
            path = paths[eventToken][argToken]
            edges = self.multiEdgeFeatureBuilder.getEdges(sentenceGraph.dependencyGraph, path)
        else:
            path = [eventToken, argToken]
            edges = None
        
        if not "disable_entity_features" in self.styles:
            self.multiEdgeFeatureBuilder.buildEntityFeatures(sentenceGraph)
        self.multiEdgeFeatureBuilder.buildPathLengthFeatures(path)
        #if not "disable_terminus_features" in self.styles:
        #    self.multiEdgeFeatureBuilder.buildTerminusTokenFeatures(path, sentenceGraph) # remove for fast
        if not "disable_single_element_features" in self.styles:
            self.multiEdgeFeatureBuilder.buildSingleElementFeatures(path, edges, sentenceGraph)
        if not "disable_ngram_features" in self.styles:
            self.multiEdgeFeatureBuilder.buildPathGrams(2, path, edges, sentenceGraph) # remove for fast
            self.multiEdgeFeatureBuilder.buildPathGrams(3, path, edges, sentenceGraph) # remove for fast
            self.multiEdgeFeatureBuilder.buildPathGrams(4, path, edges, sentenceGraph) # remove for fast
        if not "disable_path_edge_features" in self.styles:
            self.multiEdgeFeatureBuilder.buildPathEdgeFeatures(path, edges, sentenceGraph)
        #self.multiEdgeFeatureBuilder.buildSentenceFeatures(sentenceGraph)
        self.multiEdgeFeatureBuilder.setFeatureVector(None, None, None, False)
        self.multiEdgeFeatureBuilder.tag = ""
    
    def buildInterArgumentBagOfWords(self, arguments, sentenceGraph):
        if len(arguments) < 2:
            return

        indexByToken = {}
        for i in range(len(sentenceGraph.tokens)):
            indexByToken[sentenceGraph.tokens[i]] = i
        
        argTokenIndices = set()
        for arg in arguments:
            argEntity = sentenceGraph.entitiesById[arg.get("e2")]
            argToken = sentenceGraph.entityHeadTokenByEntity[argEntity]
            argTokenIndices.add(indexByToken[argToken])
        minIndex = min(argTokenIndices)
        maxIndex = max(argTokenIndices)
        self.setFeature("argBoWRange", (maxIndex-minIndex))
        self.setFeature("argBoWRange_" + str(maxIndex-minIndex), 1)
        bow = set()
        for i in range(minIndex+1, maxIndex):
            token = sentenceGraph.tokens[i]
            if len(sentenceGraph.tokenIsEntityHead[token]) == 0 and not sentenceGraph.tokenIsName[token]:
                bow.add(token.get("text"))
        bow = sorted(list(bow))
        for word in bow:
            self.setFeature("argBoW_"+word, 1)
            if word in ["/", "-"]:
                self.setFeature("argBoW_slashOrHyphen", 1)
        if len(bow) == 1:
            self.setFeature("argBoWonly_"+bow[0], 1)
            if bow[0] in ["/", "-"]:
                self.setFeature("argBoWonly_slashOrHyphen", 1)
            