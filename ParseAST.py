from graphviz import Digraph
import copy
import datetime

from pysmt.shortcuts import *
from pysmt.typing import INT

import clang.cindex
from clang.cindex import Index  #主要API
from clang.cindex import Config  #配置
from clang.cindex import CursorKind  #索引结点的类别
from clang.cindex import TypeKind    #节点的语义类别

libclangPath = r'./lib/libclang.dll'
# filename = r"whileif.c"
# filename = r"Branch_sat.c"
filename = r"Loop_sat.c"
# filename = r"Loop_sat.c"
directory = r"./TestFiles/"     # 测试文件路径

AST_root_node = None # 根节点
varsPool = []   # 初始只有位置谓词
Trans = []      # 文本类型转化集
Nodes = dict()      # 状态集

g = Digraph(name='CFA', comment="comment", format='png')    # graph object

# 配置lib,参数是传入libclang.dll路径
def configLibClang(libclangPath):
    #这个路径需要自己先在笔记本上安装	
    if Config.loaded == True:
        print("Config.loaded == True:")
        #pass
    else:
        Config.set_library_file(libclangPath)
        print("install path")

# 生成AST根节点,参数是 *.c file
def getRootNode(directory = directory, filename = filename):
    index = Index.create() # 创建AST索引
    tu = index.parse(directory + filename)  # tu:=TranslationUnit
    AST_root_node= tu.cursor  #cursor根节点
    if AST_root_node is not None:
        print("file: " + filename + " parse succeed")    # 有输出表示读取文件成功
    else:
        print("Error! file"+ filename + "parse error")
        exit(0)
    return AST_root_node

# 前序遍历函数 cursor is root node
def preorder_travers_AST(cursor):
    for cur in cursor.get_children():
        if cur.kind == CursorKind.FUNCTION_DECL:
            parseFunctionDecl(cur)
        preorder_travers_AST(cur)

class Node(object):
    id = 0 # static class variable
    '''
    每个结点有名字，有唯一ID，有自己的公式，公式如果是逻辑判断，changed就是不改变。
    changed是记录变量被修改，下次转化时候方便一些
    '''
    def __init__(self, line, formula, isCondition = False, toNodes = []):
        self.line = str(line)
        self.formula = formula  # []
        self.name = self.getName()   # Label
        self.isCondition = isCondition  # 判断是否是条件
        self.changed = self.getChanged() # line : formula
        self.toNodes = toNodes
        self.ID = Node.id
        Node.id += 1
    
    def getName(self):
        name = self.line + ":" + "".join(self.formula)
        if self.line == "-1" or self.line == "-2":
            self.formula = [''] 
        return name

    def getChanged(self):
        if self.isCondition:
            return ''
        else:
            return self.formula[0]

class Transiton(object):
    id = 0
    def __init__(self, fromNode, toNode, revered = False):
        self.ID = str(Transiton.id)
        self.fromNode = fromNode
        self.toNode = toNode
        self.revered = revered
        self.formulas = self.getFormulas()
        self.z3Formula = self.z3Formula()
        Transiton.id += 1

    def getFormulas(self):
        f1 = copy.deepcopy(self.fromNode.formula)
        f2 = unChanged([self.fromNode.changed])
        if self.fromNode.isCondition:
            if self.revered:
                return [reveredFormula(f1)] + f2
            else:
                return [f1] + f2
        else:
            f1[0] = f1[0] + "_"
            return [f1] + f2
    
    def z3Formula(self):
        z3Formula = []
        tmpForumula = copy.deepcopy(self.formulas)
        for formula in tmpForumula + [["pc","=",self.fromNode.line]] + [["pc_","=",self.toNode.line]]:
            for index in range(len(formula)):
                if isDigit(formula[index]):
                    formula[index] = "Int(" + formula[index].strip() + ")"
            if formula[1] == "=":
                exec("z3Formula.append(Equals({left},{right}))".format(left = formula[0], right = "".join(formula[2:])))
            elif formula[1] == "!=":
                exec("z3Formula.append(NotEquals({left},{right}))".format(left = formula[0], right = "".join(formula[2:])))
            elif formula[1] == "<=":
                exec("z3Formula.append(LE({left},{right}))".format(left = formula[0], right = "".join(formula[2:])))
            elif formula[1] == "<":
                exec("z3Formula.append(LT({left},{right}))".format(left = formula[0], right = "".join(formula[2:])))
            elif formula[1] == ">=":
                exec("z3Formula.append(GE({left},{right}))".format(left = formula[0], right = "".join(formula[2:])))
            elif formula[1] == ">":
                exec("z3Formula.append(GT({left},{right}))".format(left = formula[0], right = "".join(formula[2:])))
        return z3Formula
        pass

def parseFunctionDecl(FunctionDecl):
    for FunctionCompound in FunctionDecl.get_children():
        traversFuncCompoundStmt(FunctionCompound)
    pass

# Compound结点
def traversFuncCompoundStmt(CompoundStmt):
    CompoundStmtNodes = []
    ThenEndNodes = []
    ElseEndNodes = []
    gNode = None
    '''
    simple - if
    simple - while
    '''
    for node in CompoundStmt.get_children():
        if node.kind == CursorKind.IF_STMT:
            gNode, ThenEndNodes_, ElseEndNodes_ = traversIfStmt(node)
            # g.node(name=gNode.line, label=gNode.name)

            linkEndNodes2gNode(ThenEndNodes, gNode, "then-if")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-if")

            if len(ThenEndNodes+ElseEndNodes) == 0 and len(CompoundStmtNodes) > 0 :
                g.edge(CompoundStmtNodes[-1].ID, gNode.line, label="assign-if")
                Nodes[CompoundStmtNodes[-1].ID].toNodes.append(gNode.ID)

                
            ThenEndNodes = ThenEndNodes_
            ElseEndNodes = ElseEndNodes_               

        if node.kind == CursorKind.WHILE_STMT:
            gNode = traversWhileStmt(node)
            g.node(name=gNode.line, label=gNode.name)
            
            linkEndNodes2gNode(ThenEndNodes, gNode, "then-while")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-while")

            if len(ThenEndNodes+ElseEndNodes) == 0 and len(CompoundStmtNodes) > 0 :
                g.edge(CompoundStmtNodes[-1].line, gNode.line, label="assign-while")
                Nodes[CompoundStmtNodes[-1].ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.DECL_STMT:
            gNode = parseDeclStmt(node)
            # g.node(name=gNode.line, label=gNode.name)
            
            linkEndNodes2gNode(ThenEndNodes, gNode, "then-decl")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-decl")           
            
            if len(ThenEndNodes + ElseEndNodes) == 0:
                if len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="")
                    Nodes[CompoundStmtNodes[-1].ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)
        
        if node.kind == CursorKind.BINARY_OPERATOR:
            gNode = parseEvaluationStmt(node)
            # g.node(name=gNode.line, label=gNode.name)

            linkEndNodes2gNode(ThenEndNodes, gNode, "then-assign")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-assign")           
            
            if len(ThenEndNodes+ElseEndNodes) == 0:
                if len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="")
                    Nodes[CompoundStmtNodes[-1].ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.RETURN_STMT:
            return
        if node.kind == CursorKind.CALL_EXPR:
            if node.spelling == "sassert":
                gNode = parseAssertStmt(node)
                
                linkEndNodes2gNode(ThenEndNodes, gNode, "then-assert")
                linkEndNodes2gNode(ElseEndNodes, gNode, "else-assert")   

                if len(ThenEndNodes+ElseEndNodes) == 0 and len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="to-assert")
                    Nodes[CompoundStmtNodes[-1].ID].toNodes.append(gNode.ID)

                ThenEndNodes = []
                ElseEndNodes = []                
                CompoundStmtNodes.append(gNode)

# IfStmt结点
def traversIfStmt(IfStmt):
    conditionNode = None
    ThenEndNodes = []
    ElseEndNodes = []
    CompoundStmt = []
    for node in IfStmt.get_children():
        if node.kind == CursorKind.BINARY_OPERATOR: # if condition
            conditionNode = parseCondtionStmt(node)
        if node.kind == CursorKind.COMPOUND_STMT:   # if body and else body
            CompoundStmt.append(node)
    if len(CompoundStmt) != 2:
        print("Error: Code not formalized! IF-Then-Else")
        return
    ThenEndNodes = traversIfCompound(CompoundStmt[0], conditionNode)
    
    reveredformula = reveredFormula(conditionNode.formula.copy())
    line = conditionNode.line
    reveredNode = Node(line, reveredformula, True)
    Nodes[reveredNode.ID] = copy.copy(reveredNode)

    ElseEndNodes = traversIfCompound(CompoundStmt[1], reveredNode)

    return conditionNode, ThenEndNodes, ElseEndNodes

# IfStmt结点 Then块和Else块都是一样的
def traversIfCompound(CompoundStmt, conditionNode):
    CompoundStmtNodes = []
    ThenEndNodes = []
    ElseEndNodes = []
    gNode = None
    for node in CompoundStmt.get_children():
        if node.kind == CursorKind.IF_STMT:
            gNode, ThenEndNodes_, ElseEndNodes_ = traversIfStmt(node)
            # g.node(name=gNode.line, label=gNode.name)

            linkEndNodes2gNode(ThenEndNodes, gNode, "then-if")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-if")

            if len(ThenEndNodes + ElseEndNodes) == 0 :
                if len(CompoundStmtNodes) == 0 :
                    g.edge(conditionNode.line, gNode.line, label="if-if")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="assign-if")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
            
            ThenEndNodes = ThenEndNodes_
            ElseEndNodes = ElseEndNodes_                

        if node.kind == CursorKind.WHILE_STMT:
            gNode = traversWhileStmt(node)
            # g.node(name=gNode.line, label=gNode.name)

            linkEndNodes2gNode(ThenEndNodes, gNode, "then-while")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-while")

            if len(ThenEndNodes + ElseEndNodes) == 0 :
                if len(CompoundStmtNodes) == 0 :
                    g.edge(conditionNode.line, gNode.line, label="if-while")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="if-while")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []            
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.DECL_STMT:
            gNode = parseDeclStmt(node)
            # g.node(name=gNode.line, label=gNode.name)
            
            linkEndNodes2gNode(ThenEndNodes, gNode, "then-decl")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-decl")           
            
            if len(ThenEndNodes+ElseEndNodes) == 0:
                if len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(conditionNode.line, gNode.line, label="if-decl")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)
        
        if node.kind == CursorKind.BINARY_OPERATOR:
            gNode = parseEvaluationStmt(node)
            # g.node(name=gNode.line, label=gNode.name)
            
            linkEndNodes2gNode(ThenEndNodes, gNode, "then-assign")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-assign")            
            
            if len(ThenEndNodes+ElseEndNodes) == 0:
                if len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(conditionNode.line, gNode.line, label="if-assign")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.RETURN_STMT:
            return
        if node.kind == CursorKind.CALL_EXPR:
            if node.spelling == "sassert":
                gNode = parseAssertStmt(node)

                linkEndNodes2gNode(ThenEndNodes, gNode, "then-assert")
                linkEndNodes2gNode(ElseEndNodes, gNode, "else-assert")   

                if len(ThenEndNodes+ElseEndNodes) == 0 and len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="to-assert")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

                ThenEndNodes = []
                ElseEndNodes = []
                CompoundStmtNodes.append(gNode)
    if len(ThenEndNodes + ElseEndNodes) > 0:
        return ThenEndNodes + ElseEndNodes
    if len(CompoundStmtNodes) > 0:
        return [CompoundStmtNodes[-1]]
    else:
        return [conditionNode]

# WhileStmt结点
def traversWhileStmt(WhileStmt):
    conditionNode = None
    for node in WhileStmt.get_children():
        if node.kind == CursorKind.BINARY_OPERATOR:
            conditionNode = parseCondtionStmt(node)
        if node.kind == CursorKind.COMPOUND_STMT:
            traversWhileBody(node, conditionNode)
    return conditionNode

#WhileBody块
def traversWhileBody(CompoundStmt, conditionNode):
    CompoundStmtNodes = []
    ThenEndNodes = []
    ElseEndNodes = []
    gNode = None
    for node in CompoundStmt.get_children():
        if node.kind == CursorKind.IF_STMT:
            gNode, ThenEndNodes_, ElseEndNodes_ = traversIfStmt(node)
            # g.node(name=gNode.line, label=gNode.name)

            linkEndNodes2gNode(ThenEndNodes, gNode, "then-while")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-while")

            if len(ThenEndNodes + ElseEndNodes) == 0 :
                if len(CompoundStmtNodes) == 0 :
                    g.edge(conditionNode.line, gNode.line, label="while-while")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="assign-while")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

            ThenEndNodes = ThenEndNodes_
            ElseEndNodes = ElseEndNodes_               

        if node.kind == CursorKind.WHILE_STMT:
            gNode = traversWhileStmt(node)
            # g.node(name=gNode.line, label=gNode.name)

            linkEndNodes2gNode(ThenEndNodes, gNode, "then-while")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-while")

            if len(ThenEndNodes + ElseEndNodes) == 0 :
                if len(CompoundStmtNodes) == 0 :
                    g.edge(conditionNode.line, gNode.line, label="if-while")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="while-while")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

            ThenEndNodes = []
            ElseEndNodes = []            
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.DECL_STMT:
            gNode = parseDeclStmt(node)
            # g.node(name=gNode.line, label=gNode.name)
            
            linkEndNodes2gNode(ThenEndNodes, gNode, "then-decl")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-decl")           
            
            if len(ThenEndNodes+ElseEndNodes) == 0:
                if len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
                else:
                    g.edge(conditionNode.line, gNode.line, label="while-decl")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.BINARY_OPERATOR:
            gNode = parseEvaluationStmt(node)
            # g.node(name=gNode.line, label=gNode.name)
            
            linkEndNodes2gNode(ThenEndNodes, gNode, "then-assign")
            linkEndNodes2gNode(ElseEndNodes, gNode, "else-assign")            
            if len(ThenEndNodes+ElseEndNodes) == 0:
                if len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="")
                    Nodes[CompoundStmtNodes[-1].ID].toNodes.append(gNode.ID)
                else:
                    g.edge(conditionNode.line, gNode.line, label="while-assign")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)
            ThenEndNodes = []
            ElseEndNodes = []
            CompoundStmtNodes.append(gNode)

        if node.kind == CursorKind.RETURN_STMT:
            return
        if node.kind == CursorKind.CALL_EXPR:
            if node.spelling == "sassert":
                gNode = parseAssertStmt(node)
                
                linkEndNodes2gNode(ThenEndNodes, gNode, "then-assert")
                linkEndNodes2gNode(ElseEndNodes, gNode, "else-assert")   

                if len(ThenEndNodes+ElseEndNodes) == 0 and len(CompoundStmtNodes) > 0 :
                    g.edge(CompoundStmtNodes[-1].line, gNode.line, label="to-assert")
                    Nodes[conditionNode.ID].toNodes.append(gNode.ID)

                ThenEndNodes = []
                ElseEndNodes = []
                CompoundStmtNodes.append(gNode)
                
    if len(ThenEndNodes + ElseEndNodes) == 0 and len(CompoundStmtNodes) > 0:
        g.edge(CompoundStmtNodes[-1].line, conditionNode.line, label="while end")
        Nodes[CompoundStmtNodes[-1].ID].toNodes.append(conditionNode.ID)
    else:
        linkEndNodes2gNode(ThenEndNodes, conditionNode, "then-while")
        linkEndNodes2gNode(ElseEndNodes, conditionNode, "then-while")
################
# Parse Node   #
################
# 赋值
def parseEvaluationStmt(BinaryOperator):
    line, formula = parseOperator2Formula(BinaryOperator)
    node = Node(line = line, formula = formula)
    Nodes[node.ID] = copy.deepcopy(node)
    return node

# 声明
def parseDeclStmt(DeclStmt):
    line, formula = parseDecl2Formula(DeclStmt)
    node = Node(line = line, formula = formula)
    Nodes[node.ID] = copy.deepcopy(node)
    return node

# 条件 If和While中的判断条件
def parseCondtionStmt(BinaryOperator):
    line, formula = parseOperator2Formula(BinaryOperator)
    node = Node(line = line, formula = formula, isCondition = True)
    Nodes[node.ID] = copy.deepcopy(node)
    return node

# Return 
def getReturnNode(formula = "End", line = '0'):
    node = Node(line = line, formula = formula, isCondition = True)
    Nodes[int(line)] = copy.deepcopy(node)
    return node

################
# Parse  AST   #
################
# x > 3
def parseOperator2Formula(BinaryOperator):
    tokens = []
    for tk in BinaryOperator.get_tokens():
        tokens.append(tk.spelling)
    line = str(BinaryOperator.location.line)
    return line, tokens

# int a = 3;
def parseDecl2Formula(DeclStmt):
    tokens = []
    for tk in DeclStmt.get_tokens():
        tokens.append(tk.spelling)
    # 声明语句 把新变量添加到变量池中
    if tokens[1] not in varsPool:
        varsPool.append(tokens[1])
    # 赋初值
    if len(tokens) == 3: # int a ; 3个
        if tokens[0] == "int" or tokens[0] == "char":
            tokens.insert(2, "0")
        if tokens[0] == "float" or tokens[0] == "double":
            tokens.insert(2, "0.0")
        tokens.insert(2, "==")
    line = str(DeclStmt.location.line)
    return line, tokens[1:-1]

# sassert(x>3)
def parseAssertStmt(AssertStmt):
    tokens = []
    for tk in AssertStmt.get_tokens():
        tokens.append(tk.spelling)
    
    formula = tokens[2:-1]
    line = str(AssertStmt.location.line)
    node = Node(line = line, formula = formula, isCondition = True)
    Nodes[node.ID] = copy.deepcopy(node)

    # g.node(name=node.line, label=node.name)

    # 生成SAT和UNSAT结点
    satNode = getReturnNode("SAT", '-1')
    unsatNode = getReturnNode("UNSAT", '-2')
    # g.node(name = satNode.line, label = satNode.name)
    # g.node(name = unsatNode.line, label = unsatNode.name)
    # 构建 ASSERT-SAT/UNSAT 转移
    g.edge(node.line, satNode.line, "assert-sat")
    g.edge(node.line, unsatNode.line, "assert-unsat")
    Nodes[node.ID].toNodes.append(-1)
    Nodes[node.ID].toNodes.append(-2)
    return node
    pass

 把散乱的g.edge删除
 整合到for Nodes

def reveredFormula(formula):
    if formula[1] == "<":
        formula[1] = ">="
    elif formula[1] == "<=":
        formula[1] = ">"
    elif formula[1] == ">":
        formula[1] = "<="
    elif formula[1] == ">=":
        formula[1] = "<"
    elif formula[1] == "==":
        formula[1] = "!="
    elif formula[1] == "!=":
        formula[1] = "=="

    return formula
    
def unChanged(changed = []):
    f = []
    for var in varsPool:
        if var in changed or var + "_" in changed:
            continue
        f.append([var + "_", "=", var])
    return f

def linkEndNodes2gNode(EndNodes, gNode, label):
    for EndNode in EndNodes:
        g.edge(EndNode.line, gNode.line, label=label)
        Nodes[EndNode.ID].toNodes.append(gNode.ID)
    EndNodes = []

# 自己定义了一个判断字符串是否为整型数字的方法；python自带的判断字符串是否为数字的方法isdigit()好像不能判断负数，
# 比如isdigit()认为“-11”不是数字。
def isDigit(x):
    x = x.strip()
    if len(x) > 0 and x[0] == "-":
        x = x[1:]
    return x.isdigit()


def InitializedCFG():
    configLibClang(libclangPath)
    AST_root_node = getRootNode()
    starttime = datetime.datetime.now()
    preorder_travers_AST(AST_root_node)

    # Vars and tmp predicate
    Z3AllVars = dict()
    VrasDict = dict()

    # assert
    AssertList = [] # 文本格式
    AssertPreds = []
    AssertTrans = dict()

    # Symbol 会调用符号管理
    # 生成所有变量的z3变量
    for var in varsPool + ["pc"]:
        exec('globals()["{var}_"] = Symbol("{var}_", INT)'.format(var=var))
        exec('globals()["{var}"]  =  Symbol("{var}", INT)'.format(var=var))
        exec('globals()["_{var}"] = Symbol("_{var}", INT)'.format(var=var))
        exec('Z3AllVars["{var}_"]= {var}_'.format(var=var))
        exec('Z3AllVars["{var}"] =  {var}'.format(var=var))
        exec('Z3AllVars["_{var}"]= _{var}'.format(var=var))
    # 生成变量字典，将来生成替换对
    for var in varsPool + ["pc"]:
        VrasDict[var] = {var + "_" : Z3AllVars[var + "_"], var : Z3AllVars[var], "_" + var : Z3AllVars["_" + var]}
    # 生成所有表达式的z3表达式
    for ID, node in Nodes.items():
        g.node(name=node.line, label=node.name)
        for index, toID in enumerate(node.toNodes):
            toNode = Nodes[toID]
            if index > 0:
                transiton = Transiton(node,toNode, revered=True)
            else:
                transiton = Transiton(node,toNode)
            Trans.append(transiton)
        
    AssertPreds = [Equals(Z3AllVars["pc"], Int(int(node.line))) for ID, node in Nodes.items()]
    AssertTrans = dict(zip(list(range(len(Trans))), Trans))
    # assert init phi and err phi
    Assert_init = [Equals(Z3AllVars["pc"], Int(int(Nodes[0].line)))]      # assert init
    err = [trans.z3Formula for trans in Trans if trans.toNode.line == "-2"][0]
    Assert_err = [Equals(pc, Int(-2)) , err[0]]     # assert err

    print("Initialized CFG!")
    print("Vars' Count:\t", len(VrasDict), "\tTransitions Count:\t", len(Trans))
    print("All Vars and Vars' dict form")
    print(VrasDict)
    print("ALL Nodes")
    for id, node in Nodes.items():
        print("id:",id,node.toNodes,"\tline:", node.line)
    print("ALL Trans")
    for id, trans in AssertTrans.items():
        print(id, " From:", trans.fromNode.line," To:", trans.toNode.line," formula:", trans.z3Formula)
    print("Assert Preds")
    print(AssertPreds)
    print("Assert_init")
    print(Assert_init)
    print("Assert_err")
    print(Assert_err)

    endtime = datetime.datetime.now()
    print("ParseT:\t", endtime - starttime)
    return VrasDict, Z3AllVars, AssertPreds, AssertTrans, Assert_init, Assert_err

VrasDict, Z3AllVars, AssertPreds, AssertTrans, Assert_init, Assert_err= InitializedCFG()

g.view(filename=filename[0:-2] + '.gv', directory=r'./CFA')