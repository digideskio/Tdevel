try:
    import xml.etree.cElementTree as ET
except ImportError:
    import cElementTree as ET
from InteractionParseGraph import InteractionParseGraph
from InteractionXML.ParseGraph import ParseGraph
from InteractionXML.ParseGraph import ParseGraphNode
from InteractionXML.IDUtils import sortInteractionIds
#from InteractionParseGraph import InteractionParseGraphNode
import sys
import Range

def loadSentences(filename, reverseDependencies=False):
    print >> sys.stderr, "Loading file", filename
    corpusTree = ET.parse(filename)
    corpusRoot = corpusTree.getroot()
    sentenceElements = corpusRoot.find("sentences").findall("sentence")
    parseGraphsById = {}
    for sentenceElement in sentenceElements:
        print >> sys.stderr, "\rLoading sentence", sentenceElement.attrib["id"],
        elements = BioInferSentenceElements(sentenceElement)
        parseGraphsById[elements.mergedText] = GeniaParseGraph(elements, reverseDependencies)
    print >> sys.stderr, "OK"
    return parseGraphsById
        
class BioInferSentenceElements:
    def __init__(self, sentenceElement):
        self.sentence = sentenceElement
        self.mergedText = sentenceElement.attrib["origText"].strip()
        self.mergedText = self.mergedText.replace(" ","").lower()
        #self.entities = []
        #self.entitiesById = {}
        #self.pairs = []
        #self.interactions = []
        self.tokens = []
        self.dependencies = []
        
        self.tokens = sentenceElement.findall("token")
        self.dependencies = sentenceElement.find("linkages").find("linkage").findall("link")

class GeniaEntity:
    def __init__(self):
        self.id = "unknown"
        self.elementType = "unknown"
        self.sem = "unknown"
        self.charOffset = None
        self.headToken = None
        self.text = "unknown"
        self.InteractionXMLelement = None
    
    def toString(self):
        return "Entity: "+self.id+","+self.elementType+","+self.sem+","+str(self.charOffset)+",\""+self.text+"\""
    
    def toElement(self, sentenceId, entitiesById):
        entityElement = ET.Element("entity")
        entityElement.attrib["origId"] = self.id
        entityElement.attrib["id"] = sentenceId + ".e" + str(len(entitiesById))
        entitiesById[self.id] = entityElement
        entityElement.attrib["type"] = self.sem
        if self.sem == "gene-or-gene-product":
            entityElement.attrib["isName"] = "True"
        else:
            entityElement.attrib["isName"] = "False"
        entityElement.attrib["charOffset"] = Range.tuplesToCharOffset(self.charOffset)
        #entityElement.attrib["headOffset"] = entityElement.attrib["charOffset"]
#        if self.headToken != None:
#            entityElement.attrib["headOffset"] = Range.tuplesToCharOffset(self.headToken.charOffset)
#        else:
#            entityElement.attrib["headOffset"] = interactionWordElement.attrib["charOffset"]
        entityElement.attrib["text"] = self.text
        self.InteractionXMLelement = entityElement
        
class GeniaEvent:
    def __init__(self):
        self.id = "unknown"
        #self.e1 = None
        #self.e1Type = "unknown"
        #self.e2 = None
        #self.e2Type = "unknown"
        self.type = "unknown"
        self.themes = []
        self.causes = []
        self.scatters = []
        self.clueTypeCharOffsets = []
        self.clueTypeTexts = []
        self.corefThemeCharOffsets = []
        self.corefThemeTexts = []
        self.corefCauseCharOffsets = []
        self.corefCauseTexts = []
        self.corefCauseEntity = None
        self.corefThemeEntity = None
        self.headToken = None
    
    def toString(self):
        return "Event: "+self.id+","+self.type+", Themes:"+str(self.themes)+", Causes:"+str(self.causes)+", clueTypes:"+str(self.clueTypeCharOffsets)+","+str(self.clueTypeTexts)
    
    def interactionWordToElement(self, sentenceId, entitiesById):   
        interactionWordElement = None
#        for entity in entitiesById.values():
#            if entity.attrib["charOffset"] == Range.tuplesToCharOffset(self.clueTypeCharOffsets):
#                interactionWordElement = entity
#                interactionWordElement.attrib["type"] = self.type
#                interactionWordElement.attrib["isName"] = "False"
#                break
        if interactionWordElement == None:
            interactionWordElement = ET.Element("entity")
            interactionWordElement.attrib["origId"] = self.id
            interactionWordElement.attrib["type"] = self.type
            interactionWordElement.attrib["isName"] = "False"
            interactionWordElement.attrib["charOffset"] = Range.tuplesToCharOffset(self.clueTypeCharOffsets)
            if interactionWordElement.attrib["charOffset"] == "":
                return
#            if self.headToken != None:
#                interactionWordElement.attrib["headOffset"] = Range.tuplesToCharOffset(self.headToken.charOffset)
#            else:
#                interactionWordElement.attrib["headOffset"] = interactionWordElement.attrib["charOffset"]
            interactionWordElement.attrib["text"] = str(self.clueTypeTexts)
            interactionWordElement.attrib["id"] = sentenceId + ".e" + str(len(entitiesById))
            entitiesById[self.id] = interactionWordElement
    
#    def __getIdrefOffsets(self, element):
#        idref = ""        
    
    def addInteractionElement(self, entity1, entity2, origId, type, interactionsById, sentenceId):
        interactionElement = ET.Element("interaction")
        interactionElement.attrib["origId"] = origId
        interactionElement.attrib["type"] = type
        interactionElement.attrib["directed"] = "True"
        interactionElement.attrib["e1"] = entity1.attrib["id"]
        interactionElement.attrib["e2"] = entity2.attrib["id"]
        interactionElement.attrib["id"] = sentenceId + ".i" + str(len(interactionsById))
        interactionsById[interactionElement.attrib["id"]] = interactionElement
    
    def toElements(self, sentenceId, entitiesById, interactionsById):
        if entitiesById.has_key(self.id):
            interactionWordElement = entitiesById[self.id]
        else:
            return
        if self.corefThemeEntity != None:
            self.addInteractionElement(interactionWordElement, self.corefThemeEntity.InteractionXMLelement, self.id, "theme", interactionsById, sentenceId)
        for theme in self.themes:
            if entitiesById.has_key(theme):
                targetEntity = entitiesById[theme]
                if self.corefThemeEntity == None:
                    self.addInteractionElement(interactionWordElement, targetEntity, self.id, "theme", interactionsById, sentenceId)
                else:
                    self.addInteractionElement(self.corefThemeEntity.InteractionXMLelement, targetEntity, self.id, "coref", interactionsById, sentenceId)
        if self.corefCauseEntity != None:
            self.addInteractionElement(interactionWordElement, self.corefCauseEntity.InteractionXMLelement, self.id, "theme", interactionsById, sentenceId)
        for cause in self.causes:
            if entitiesById.has_key(cause):
                targetEntity = entitiesById[cause]
                if self.corefCauseEntity == None:
                    self.addInteractionElement(interactionWordElement, targetEntity, self.id, "cause", interactionsById, sentenceId)
                else:
                    self.addInteractionElement(self.corefCauseEntity.InteractionXMLelement, targetEntity, self.id, "coref", interactionsById, sentenceId)
        for scatter in self.scatters:
            # scatters abuse the way the Event-class should work
            if entitiesById.has_key(scatter):
                targetEntity = entitiesById[scatter]
                self.addInteractionElement(interactionWordElement, targetEntity, self.id, "scatter", interactionsById, sentenceId)
        
class GeniaParseGraph(InteractionParseGraph):
    
    def __init__(self, sentence, reverseDependencies=False):
        self.sentence = sentence
        self.tokensById, self.dependenciesById = self.buildParseGraphFromBioInfer(sentence.tokens, sentence.dependencies, reverseDependencies)
        
        self.interactionGraphDependencies = []
        
        self.sentence.annotationDependencies = []
        self.sentence.annotationDependenciesWithParseDependency = 0
        
        self.eventsById = {}
        self.tokenHeadScores = None
    
    def writeToInteractionXML(self, documentElement, sentenceCount):
        sentenceElement = ET.Element("sentence")
        sentenceId = documentElement.attrib["id"] + ".s" + str(sentenceCount)
        sentenceElement.attrib["id"] = sentenceId
        sentenceElement.attrib["origId"] = self.origGeniaDocumentId + "." + self.origGeniaId
        sentenceElement.attrib["text"] = self.sentence.sentence.attrib["origText"]
        entitiesById = {}
        interactionsById = {}
        
        keys = self.geniaEntitiesById.keys()
        keys.sort()
        for key in keys:
            self.geniaEntitiesById[key].toElement(sentenceId, entitiesById)
        keys = self.eventsById.keys()
        keys.sort()
        for key in keys:
            self.eventsById[key].interactionWordToElement(sentenceId, entitiesById)
        for key in keys:
            self.eventsById[key].toElements(sentenceId, entitiesById, interactionsById)
        
        keys = entitiesById.keys()
        keys.sort()#sortInteractionIds)
        for key in keys:
            sentenceElement.append(entitiesById[key])
            
        keys = interactionsById.keys()
        keys.sort()#sortInteractionIds)
        for key in keys:
            sentenceElement.append(interactionsById[key])
        
        self.addParseElements(sentenceElement)
        documentElement.append(sentenceElement)
    
    def buildParseGraphFromBioInfer(self, tokenElements, dependencyElements, reverseDependencies=False):
        """ Returns dictionaries containing tokens and dependencies
        of the graph generated from ElementTree-elements.
        """
        tokensById = {}
        tokensByOrigId = {}
        dependenciesById = {}
        prevOffset = -1000
        for tokenElement in tokenElements:
            node = ParseGraphNode()
            
            node.origid = tokenElement.attrib["id"]
            node.id = len(tokensById)+1
            if tokenElement.attrib.has_key("POS"):
                node.pos = tokenElement.attrib["POS"]
            else:
                node.pos = "N/A"
            subtokenElement = tokenElement.find("subtoken")
            node.text = subtokenElement.attrib["text"]
            charFrom = int(tokenElement.attrib["charOffset"])
            assert(prevOffset < charFrom)
            prevOffset = charFrom
            charTo = charFrom + len(subtokenElement.attrib["text"])-1
            node.charOffset = (charFrom, charTo)
            tokensById[node.id] = node
            tokensByOrigId[node.origid] = node
    
        #self.depByOrder = []
        dependencyIndex = len(tokensById) + 99
        for dependencyElement in dependencyElements:
            if dependencyElement.attrib["token1"] == dependencyElement.attrib["token2"]:
                continue
            
            dependency = ParseGraphNode(True)
            dependency.dependencyType = dependencyElement.attrib["type"]
            if dependency.dependencyType[0] == "<":
                dependency.to = tokensByOrigId[dependencyElement.attrib["token1"]]
                dependency.fro = tokensByOrigId[dependencyElement.attrib["token2"]]
                if reverseDependencies:
                    dependency.fro, dependency.to = dependency.to, dependency.fro
                dependency.dependencyType = dependency.dependencyType[1:]
            elif dependency.dependencyType[-1] == ">":
                dependency.fro = tokensByOrigId[dependencyElement.attrib["token1"]]
                dependency.to = tokensByOrigId[dependencyElement.attrib["token2"]]
                if reverseDependencies:
                    dependency.fro, dependency.to = dependency.to, dependency.fro
                dependency.dependencyType = dependency.dependencyType[:-1]
            else:
                sys.exit("Couldn't solve dependency type")
            
            tokensById[dependency.fro.id].dependencies.append(dependency)
            tokensById[dependency.to.id].dependencies.append(dependency)
            #dependenciesById["dep_" + str(dependencyIndex) + "-mt_" + str(dependency.fro.id) + "-" + dependency.dependencyType + "-mt_" + str(dependency.to.id)] = dependency
            #dependenciesById[dependencyIndex] = dependency
            dependency.id = dependencyIndex # (dependency.fro.id,dependency.to.id)
            assert( not dependenciesById.has_key(dependency.id) )
            dependenciesById[dependency.id] = dependency
            dependencyIndex += 1
        
        return tokensById, dependenciesById
    
    def writeEntityList(self, builder):
        keys = self.geniaEntitiesById.keys()
        keys.sort()
        for key in keys:
            builder.span(self.geniaEntitiesById[key].toString())
            builder.lineBreak()
    
    def writeEventList(self, builder):
        keys = self.eventsById.keys()
        keys.sort()
        for key in keys:
            builder.span(self.eventsById[key].toString())
            builder.lineBreak()
    
    def __addNestedEntities(self, text, children):
        for child in children:
            #assert(child.tag == "term")
            entity = GeniaEntity()
            entity.elementType = child.tag
            if child.attrib.has_key("sem"):
                entity.sem = child.attrib["sem"]
            elif child.tag == "gene-or-gene-product":
                entity.sem = "gene-or-gene-product"
            entity.id = child.attrib["id"]
            text = text.replace("\n"," ")
            charOffsetBegin = len(text)
            if child.text != None:
                text += child.text
            text = self.__addNestedEntities(text,child.getchildren())
            text = text.replace("\n"," ")
            charOffsetEnd = len(text)-1
            if child.tail != None:
                text += child.tail
            entity.charOffset = (charOffsetBegin, charOffsetEnd)
            entity.text = text[charOffsetBegin:charOffsetEnd+1]
            self.geniaEntitiesById[entity.id] = entity
        return text
    
    def addEntities(self, sentenceElement):
        self.geniaEntitiesById = {}
        text = sentenceElement.text
        if text == None: text = ""
        self.__addNestedEntities(text, sentenceElement.getchildren())

    def addCorefEntities(self, event):
        event.corefThemeEntity = None
        if len(event.corefThemeTexts) > 0:
            # TODO: Solve coref=multilayer cases
            #assert(len(event.corefThemeTexts) == 1)
            entity = GeniaEntity()
            entity.elementType = "undefined"
            entity.sem = "coref"       
            entity.id = event.id + "_corefTheme"
            entity.charOffset = event.corefThemeCharOffsets[0]
            entity.text = event.corefThemeTexts[0]
            self.geniaEntitiesById[entity.id] = entity
            event.corefThemeEntity = entity
        event.corefCauseEntity = None
        if len(event.corefCauseTexts) > 0:
            # TODO: Solve coref=multilayer cases
            #assert(len(event.corefCauseTexts) == 1)
            entity = GeniaEntity()
            entity.elementType = "undefined"
            entity.sem = "coref"       
            entity.id = event.id + "_corefCause"
            entity.charOffset = event.corefCauseCharOffsets[0]
            entity.text = event.corefCauseTexts[0]
            self.geniaEntitiesById[entity.id] = entity
            event.corefCauseEntity = entity
    
    def __findNestedEventTextBinding(self, text, children, event):
        for child in children:
            text = text.replace("\n"," ")
            charOffsetBegin = len(text)
            if child.text != None:
                text += child.text
            text = self.__findNestedEventTextBinding(text,child.getchildren(),event)
            text = text.replace("\n"," ")
            charOffsetEnd = len(text)-1
            if child.tail != None:
                text += child.tail
            text = text.replace("\n"," ")
            if child.tag == "clueType":
                event.clueTypeCharOffsets.append( (charOffsetBegin, charOffsetEnd) )
                event.clueTypeTexts.append( text[charOffsetBegin:charOffsetEnd+1] )
            if child.tag == "corefTheme":
                event.corefThemeCharOffsets.append( (charOffsetBegin, charOffsetEnd) )
                event.corefThemeTexts.append( text[charOffsetBegin:charOffsetEnd+1] )
            if child.tag == "corefCause":
                event.corefCauseCharOffsets.append( (charOffsetBegin, charOffsetEnd) )
                event.corefCauseTexts.append( text[charOffsetBegin:charOffsetEnd+1] )
        return text
    
    def findEventTextBinding(self, eventElement, event):
        clueElement = eventElement.find("clue")
        if clueElement != None:
            text = clueElement.text
            if text == None: text = ""
            self.__findNestedEventTextBinding(text, clueElement.getchildren(), event)
    
    def addEvent(self, eventElement):
        event = GeniaEvent()
        event.id = eventElement.attrib["id"]
        if eventElement.find("type").attrib.has_key("class"):
            event.type = eventElement.find("type").attrib["class"]
        self.findEventTextBinding(eventElement, event)
        self.addCorefEntities(event)
        # What is the difference between one theme/cause element having multiple idrefs, or there
        # being multiple theme/cause elements with one idref each?
        themeElements = eventElement.findall("theme")
        for themeElement in themeElements:
            event.themes.append(themeElement.attrib["idref"])
        causeElements = eventElement.findall("cause")
        for causeElement in causeElements:
            event.causes.append(causeElement.attrib["idref"])
        assert(not self.eventsById.has_key(event.id))
        self.eventsById[event.id] = event
        # Add possible scatter events
        for themeElement in themeElements:
            self.addScatterEvent(themeElement)
        for causeElement in causeElements:
            self.addScatterEvent(causeElement)

    def getHeadTokenByGeniaId(self, geniaId):
        token = None
        if self.geniaEntitiesById.has_key(geniaId):
            token = self.geniaEntitiesById[geniaId].headToken
        elif self.eventsById.has_key(geniaId):
            token = self.eventsById[geniaId].headToken
        return token
    
    def mapEventsToParse(self):
        self.__findHeadTokensForEventsAndEntities()
        for event in self.eventsById.values():
            clueTypeToken = event.headToken
            if clueTypeToken == None:
                continue
            for theme in event.themes:
                themeToken = self.getHeadTokenByGeniaId(theme)
                if themeToken != None and themeToken != clueTypeToken:
                    assert(clueTypeToken.id != themeToken.id)
                    self.addAnnotationDependency(clueTypeToken.id-1, themeToken.id-1, "theme", "UNIDIRECTIONAL")
            for cause in event.causes:
                causeToken = self.getHeadTokenByGeniaId(cause)
                if causeToken != None and causeToken != clueTypeToken:
                    assert(clueTypeToken.id != causeToken.id)
                    self.addAnnotationDependency(clueTypeToken.id-1, causeToken.id-1, "cause", "UNIDIRECTIONAL")
    
    def scoreTokens(self):
        if self.tokenHeadScores != None:
            return self.tokenHeadScores
        else:
            self.tokenHeadScores = {}
        tokenKeys = self.tokensById.keys()
        tokenKeys.sort()
        depTypesToRemove = ["nn", "det", "hyphen", "num", "amod", "nmod", "appos", "measure", "dep"]
        depTypesToRemoveReverse = ["A/AN"]
        for key in tokenKeys:
            if len(self.tokensById[key].dependencies) > 0:
                self.tokenHeadScores[key] = 1
            else:
                self.tokenHeadScores[key] = 0
        modifiedScores = True
        while modifiedScores == True:
            modifiedScores = False
            for i in tokenKeys:
                tokenI = self.tokensById[i]
                for j in tokenKeys:
                    tokenJ = self.tokensById[j]
                    for dep in tokenI.dependencies:
                        if dep.to == tokenI and dep.fro == tokenJ and (dep.dependencyType in depTypesToRemove):
                            #tokenScores[i] -= 1
                            if self.tokenHeadScores[j] <= self.tokenHeadScores[i]:
                                self.tokenHeadScores[j] = self.tokenHeadScores[i] + 1
                                modifiedScores = True
                        elif dep.fro == tokenI and dep.to == tokenJ and (dep.dependencyType in depTypesToRemoveReverse):
                            #tokenScores[i] -= 1
                            if self.tokenHeadScores[j] <= self.tokenHeadScores[i]:
                                self.tokenHeadScores[j] = self.tokenHeadScores[i] + 1
                                modifiedScores = True
        return self.tokenHeadScores 
    
    def findHeadToken(self, charOffsets):
        debug = False
        tokenKeys = self.tokensById.keys()
        tokenKeys.sort()
        candidateTokenIds = set()
        for charOffset in charOffsets:
            for key in tokenKeys:
                token = self.tokensById[key]
                if Range.overlap(charOffset, token.charOffset):
                    candidateTokenIds.add(token.id)
                    #if token.text == "Leukotriene":
                    #    debug = True
        candidateTokenIds = list(candidateTokenIds)
        candidateTokenIds.sort()
        
        tokenHeadScores = self.scoreTokens()
        
        #if debug:
        #    print "Tokens:", candidateTokenIds
        #    print "Scores:", tokenScores
        
        if len(candidateTokenIds) == 0:
            return None
        
        highestScore = -9999999
        bestTokens = []
        for i in candidateTokenIds:
            if tokenHeadScores[i] > highestScore:
                highestScore = tokenHeadScores[i]
        for i in range(len(candidateTokenIds)):
            if tokenHeadScores[candidateTokenIds[i]] == highestScore:
                bestTokens.append(candidateTokenIds[i])
        if debug:
            print "tokens:"
            for i in range(len(candidateTokenIds)):
                print "[", candidateTokenIds[i], self.tokensById[candidateTokenIds[i]].text, tokenHeadScores[candidateTokenIds[i]], "]"
        return self.tokensById[bestTokens[-1]]
        assert(False)    
    
    def findHeadTokenSimple(self, charOffsets):
        # Takes always leftmost token
        tokenKeys = self.tokensById.keys()
        tokenKeys.sort()
        candidateTokens = set()
        for charOffset in charOffsets:
            for key in tokenKeys:
                token = self.tokensById[key]
                if Range.overlap(charOffset, token.charOffset):
                    candidateTokens.add(token.id)
        if len(candidateTokens)==0:
            return None
        else:
            candidateTokens = list(candidateTokens)
            candidateTokens.sort()
            return self.tokensById[candidateTokens[0]]
    
    def __findHeadTokensForEventsAndEntities(self):
        for entity in self.geniaEntitiesById.values():
            entity.headToken = self.findHeadToken([entity.charOffset])
        for event in self.eventsById.values():
            event.headToken = self.findHeadToken(event.clueTypeCharOffsets)
            
    def addParseElements(self, sentenceElement):
        sentenceAnalysesElement = ET.Element("sentenceanalyses")
        sentenceElement.append(sentenceAnalysesElement)
        parsesElement = ET.Element("parses")
        sentenceAnalysesElement.append(parsesElement)
        parseElement = ET.Element("parse")
        parseElement.attrib["parser"] = "gold"
        parseElement.attrib["tokenizer"] = "gold"
        parsesElement.append(parseElement)
        keys = self.dependenciesById.keys()
        keys.sort()
        depId = 1
        for key in keys:            
            dependency = self.dependenciesById[key]
            dependencyElement = ET.Element("dependency")
            dependencyElement.attrib["id"] = "gsp_"+str(depId)
            dependencyElement.attrib["type"] = dependency.dependencyType
            dependencyElement.attrib["t1"] = "gst_"+str(dependency.fro.id)
            dependencyElement.attrib["t2"] = "gst_"+str(dependency.to.id)
            parseElement.append(dependencyElement)
            depId += 1
        tokenizationsElement = ET.Element("tokenizations")
        sentenceAnalysesElement.append(tokenizationsElement)
        tokenizationElement = ET.Element("tokenization")
        tokenizationElement.attrib["tokenizer"] = "gold"
        tokenizationsElement.append(tokenizationElement)
        keys = self.tokensById.keys()
        keys.sort()
        for key in keys:
            token = self.tokensById[key]
            tokenElement = ET.Element("token")
            tokenElement.attrib["id"] = "gst_"+str(key)
            tokenElement.attrib["POS"] = token.pos
            tokenElement.attrib["text"] = token.text
            tokenElement.attrib["charOffset"] = Range.tuplesToCharOffset(token.charOffset)
            tokenizationElement.append(tokenElement)
    
    def addScatterEvent(self, element):
        if not element.attrib.has_key("idref1"):
            return # only one idref

        if not self.geniaEntitiesById.has_key(element.attrib["idref"]):
            return
        iwEntity = self.geniaEntitiesById[element.attrib["idref"]]
        
        newEvent = GeniaEvent()
        newEvent.id = "scatter_" + iwEntity.id
        newEvent.type = iwEntity.sem
        newEvent.clueTypeCharOffsets = [iwEntity.charOffset]
        newEvent.headToken = iwEntity.headToken
        newEvent.clueTypeTexts = iwEntity.text
        
        # numbered idrefs
        keys = element.attrib.keys()
        keys.sort()
        for key in keys:
            if key[0:5] == "idref" and len(key) > 5:
                newEvent.scatters.append(element.attrib[key])
                newEvent.id += "_" + element.attrib[key]
        
        if not self.eventsById.has_key(newEvent.id):
            self.eventsById[newEvent.id] = newEvent