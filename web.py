from flask import Flask, render_template_string, request, jsonify, send_file
from datetime import datetime
import re
import io

app = Flask(__name__)

class Token:
    def __init__(self, tipo, valor, linea, columna):
        self.tipo = tipo
        self.valor = valor
        self.linea = linea
        self.columna = columna
    
    def to_dict(self):
        return {
            'tipo': self.tipo,
            'valor': self.valor,
            'linea': self.linea,
            'columna': self.columna
        }

class Error:
    def __init__(self, linea, columna, mensaje, sugerencia, tipo='lexico'):
        self.linea = linea
        self.columna = columna
        self.mensaje = mensaje
        self.sugerencia = sugerencia
        self.tipo = tipo  # 'lexico' o 'sintactico'
    
    def to_dict(self):
        return {
            'linea': self.linea,
            'columna': self.columna,
            'mensaje': self.mensaje,
            'sugerencia': self.sugerencia,
            'tipo': self.tipo
        }

class AnalizadorLexico:
    def __init__(self):
        # Palabras reservadas exactas (sensible a mayúsculas/minúsculas)
        self.palabras_reservadas = [
            'si', 'sino', 'mientras', 'para', 'entero', 'flotante', 
            'cadena', 'retornar', 'funcion', 'verdadero', 'falso', 
            'imprimir', 'leer'
        ]
        
        self.operadores_dobles = ['==', '!=', '<=', '>=', '&&', '||']
        self.operadores_simples = ['+', '-', '*', '/', '%', '<', '>', '!', '=']
        self.delimitadores = ['(', ')', '{', '}', ';', ',']
    
    def es_palabra_reservada_valida(self, palabra):
        """Verifica si la palabra es exactamente una palabra reservada (case-sensitive)"""
        return palabra in self.palabras_reservadas
    
    def sugerir_palabra_reservada(self, palabra):
        """Sugiere la palabra reservada correcta si está mal escrita"""
        palabra_lower = palabra.lower()
        
        # Buscar coincidencias exactas en minúsculas
        if palabra_lower in self.palabras_reservadas:
            return palabra_lower
        
        # Sugerencias para errores comunes
        sugerencias = {
            'if': 'si',
            'else': 'sino',
            'while': 'mientras',
            'for': 'para',
            'int': 'entero',
            'float': 'flotante',
            'string': 'cadena',
            'return': 'retornar',
            'function': 'funcion',
            'true': 'verdadero',
            'false': 'falso',
            'print': 'imprimir',
            'read': 'leer',
            'sipasa': 'si',  # Error común
            'sinos': 'sino',
            'enteo': 'entero',
            'flotate': 'flotante',
        }
        
        if palabra_lower in sugerencias:
            return sugerencias[palabra_lower]
        
        # Buscar palabras similares por distancia de edición simple
        for reservada in self.palabras_reservadas:
            if self.distancia_similar(palabra_lower, reservada):
                return reservada
        
        return None
    
    def distancia_similar(self, palabra1, palabra2):
        """Verifica si dos palabras son similares (1-2 caracteres de diferencia)"""
        if abs(len(palabra1) - len(palabra2)) > 2:
            return False
        
        diferencias = 0
        for i in range(min(len(palabra1), len(palabra2))):
            if palabra1[i] != palabra2[i]:
                diferencias += 1
            if diferencias > 2:
                return False
        
        return True
    
    def analizar(self, codigo):
        tokens = []
        errores = []
        lineas = codigo.split('\n')
        
        for num_linea, linea in enumerate(lineas, 1):
            pos = 0
            
            while pos < len(linea):
                if linea[pos].isspace():
                    pos += 1
                    continue
                
                # Comentarios de línea
                if pos < len(linea) - 1 and linea[pos:pos+2] == '//':
                    tokens.append(Token('COMENTARIO', linea[pos:], num_linea, pos + 1))
                    break
                
                # Comentarios de bloque
                if pos < len(linea) - 1 and linea[pos:pos+2] == '/*':
                    fin_comentario = linea.find('*/', pos + 2)
                    if fin_comentario != -1:
                        tokens.append(Token('COMENTARIO', linea[pos:fin_comentario+2], num_linea, pos + 1))
                        pos = fin_comentario + 2
                    else:
                        tokens.append(Token('COMENTARIO', linea[pos:], num_linea, pos + 1))
                        errores.append(Error(num_linea, pos + 1,
                                           "Comentario de bloque sin cerrar",
                                           "Agregar */ al final del comentario"))
                        break
                    continue
                
                # Cadenas de texto
                if linea[pos] in ['"', "'"]:
                    comilla = linea[pos]
                    fin_cadena = pos + 1
                    escapado = False
                    
                    while fin_cadena < len(linea):
                        if linea[fin_cadena] == '\\' and not escapado:
                            escapado = True
                            fin_cadena += 1
                            continue
                        if linea[fin_cadena] == comilla and not escapado:
                            break
                        escapado = False
                        fin_cadena += 1
                    
                    if fin_cadena < len(linea):
                        tokens.append(Token('LITERAL_CADENA', linea[pos:fin_cadena+1], num_linea, pos + 1))
                        pos = fin_cadena + 1
                    else:
                        errores.append(Error(num_linea, pos + 1, 
                                           f"Cadena sin cerrar",
                                           f"Agregar {comilla} al final de la cadena"))
                        pos = len(linea)
                    continue
                
                # Números
                if linea[pos].isdigit():
                    inicio_num = pos
                    numero = ''
                    tiene_decimal = False
                    
                    while pos < len(linea) and (linea[pos].isdigit() or linea[pos] == '.'):
                        if linea[pos] == '.':
                            if tiene_decimal:
                                errores.append(Error(num_linea, inicio_num + 1,
                                                   f"Número con múltiples puntos decimales: {numero + linea[pos]}",
                                                   "Usar solo un punto decimal"))
                                break
                            tiene_decimal = True
                        numero += linea[pos]
                        pos += 1
                    
                    if pos < len(linea) and (linea[pos].isalpha() or linea[pos] == '_'):
                        invalido = numero
                        while pos < len(linea) and (linea[pos].isalnum() or linea[pos] == '_'):
                            invalido += linea[pos]
                            pos += 1
                        errores.append(Error(num_linea, inicio_num + 1,
                                           f"Identificador inválido: '{invalido}'",
                                           "Los identificadores no pueden comenzar con números"))
                    else:
                        tipo = 'LITERAL_FLOTANTE' if tiene_decimal else 'LITERAL_ENTERO'
                        tokens.append(Token(tipo, numero, num_linea, inicio_num + 1))
                    continue
                
                # Operadores de dos caracteres
                if pos < len(linea) - 1 and linea[pos:pos+2] in self.operadores_dobles:
                    tokens.append(Token('OPERADOR', linea[pos:pos+2], num_linea, pos + 1))
                    pos += 2
                    continue
                
                # Operadores de un carácter
                if linea[pos] in self.operadores_simples:
                    tokens.append(Token('OPERADOR', linea[pos], num_linea, pos + 1))
                    pos += 1
                    continue
                
                # Delimitadores
                if linea[pos] in self.delimitadores:
                    tokens.append(Token('DELIMITADOR', linea[pos], num_linea, pos + 1))
                    pos += 1
                    continue
                
                # Identificadores y palabras reservadas
                if linea[pos].isalpha() or linea[pos] == '_':
                    inicio_id = pos
                    identificador = ''
                    
                    while pos < len(linea) and (linea[pos].isalnum() or linea[pos] == '_'):
                        identificador += linea[pos]
                        pos += 1
                    
                    # Verificar si es palabra reservada EXACTA
                    if self.es_palabra_reservada_valida(identificador):
                        tokens.append(Token('PALABRA_RESERVADA', identificador, num_linea, inicio_id + 1))
                    else:
                        # Verificar si es una palabra reservada mal escrita
                        sugerencia = self.sugerir_palabra_reservada(identificador)
                        if sugerencia and identificador.lower() in [pr.lower() for pr in self.palabras_reservadas]:
                            errores.append(Error(num_linea, inicio_id + 1,
                                               f"Palabra reservada mal escrita: '{identificador}'",
                                               f"¿Quisiste decir '{sugerencia}'? Las palabras reservadas son sensibles a mayúsculas/minúsculas"))
                            tokens.append(Token('ERROR_PALABRA_RESERVADA', identificador, num_linea, inicio_id + 1))
                        elif sugerencia:
                            errores.append(Error(num_linea, inicio_id + 1,
                                               f"Posible palabra reservada mal escrita: '{identificador}'",
                                               f"¿Quisiste decir '{sugerencia}'?"))
                            tokens.append(Token('IDENTIFICADOR', identificador, num_linea, inicio_id + 1))
                        else:
                            tokens.append(Token('IDENTIFICADOR', identificador, num_linea, inicio_id + 1))
                    continue
                
                # Caracter no reconocido
                errores.append(Error(num_linea, pos + 1,
                                   f"Caracter no reconocido: '{linea[pos]}'",
                                   "Verificar si es un operador o símbolo válido"))
                pos += 1
        
        return tokens, errores
    
    def generar_log(self, tokens, nombre_archivo):
        log = "=" * 60 + "\n"
        log += "=== ANÁLISIS LÉXICO - LOG ===\n"
        log += "=" * 60 + "\n"
        log += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        log += f"Archivo: {nombre_archivo}\n"
        log += f"Total de tokens: {len(tokens)}\n"
        log += "=" * 60 + "\n\n"
        
        for i, token in enumerate(tokens, 1):
            log += f"Token {i}:\n"
            log += f"  Tipo: {token.tipo}\n"
            log += f"  Valor: {token.valor}\n"
            log += f"  Línea: {token.linea}, Columna: {token.columna}\n"
            log += "-" * 40 + "\n"
        
        return log

class AnalizadorSintactico:
    """Analiza la estructura sintáctica del código"""
    
    def __init__(self):
        self.errores = []
    
    def analizar(self, tokens, codigo):
        self.errores = []
        
        # Verificar paréntesis, llaves y punto y coma
        self.verificar_delimitadores(tokens)
        self.verificar_estructura_basica(tokens)
        self.verificar_declaraciones(tokens)
        
        return self.errores
    
    def verificar_delimitadores(self, tokens):
        """Verifica que paréntesis y llaves estén balanceados"""
        pila_parentesis = []
        pila_llaves = []
        
        for token in tokens:
            if token.tipo == 'DELIMITADOR':
                if token.valor == '(':
                    pila_parentesis.append(token)
                elif token.valor == ')':
                    if not pila_parentesis:
                        self.errores.append(Error(token.linea, token.columna,
                                                 "Paréntesis de cierre ')' sin paréntesis de apertura",
                                                 "Agregar '(' antes o eliminar ')'",
                                                 'sintactico'))
                    else:
                        pila_parentesis.pop()
                
                elif token.valor == '{':
                    pila_llaves.append(token)
                elif token.valor == '}':
                    if not pila_llaves:
                        self.errores.append(Error(token.linea, token.columna,
                                                 "Llave de cierre '}' sin llave de apertura",
                                                 "Agregar '{' antes o eliminar '}'",
                                                 'sintactico'))
                    else:
                        pila_llaves.pop()
        
        # Verificar que no queden delimitadores sin cerrar
        for token in pila_parentesis:
            self.errores.append(Error(token.linea, token.columna,
                                     "Paréntesis '(' sin cerrar",
                                     "Agregar ')' al final de la expresión",
                                     'sintactico'))
        
        for token in pila_llaves:
            self.errores.append(Error(token.linea, token.columna,
                                     "Llave '{' sin cerrar",
                                     "Agregar '}' al final del bloque",
                                     'sintactico'))
    
    def verificar_estructura_basica(self, tokens):
        """Verifica estructuras básicas como if, while"""
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token.tipo == 'PALABRA_RESERVADA':
                # Verificar estructura de 'si'
                if token.valor == 'si':
                    if i + 1 >= len(tokens) or tokens[i + 1].valor != '(':
                        self.errores.append(Error(token.linea, token.columna,
                                                 "Falta paréntesis '(' después de 'si'",
                                                 "La estructura debe ser: si (condicion) { ... }",
                                                 'sintactico'))
                
                # Verificar estructura de 'mientras'
                elif token.valor == 'mientras':
                    if i + 1 >= len(tokens) or tokens[i + 1].valor != '(':
                        self.errores.append(Error(token.linea, token.columna,
                                                 "Falta paréntesis '(' después de 'mientras'",
                                                 "La estructura debe ser: mientras (condicion) { ... }",
                                                 'sintactico'))
                
                # Verificar estructura de 'para'
                elif token.valor == 'para':
                    if i + 1 >= len(tokens) or tokens[i + 1].valor != '(':
                        self.errores.append(Error(token.linea, token.columna,
                                                 "Falta paréntesis '(' después de 'para'",
                                                 "La estructura debe ser: para (init; cond; incr) { ... }",
                                                 'sintactico'))
            
            i += 1
    
    def verificar_declaraciones(self, tokens):
        """Verifica que las declaraciones tengan la estructura correcta"""
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            # Verificar declaración de variables (tipo identificador = valor;)
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in ['entero', 'flotante', 'cadena']:
                # Debe seguir un identificador
                if i + 1 >= len(tokens):
                    self.errores.append(Error(token.linea, token.columna,
                                             f"Declaración de '{token.valor}' incompleta",
                                             f"Debe seguir: {token.valor} identificador = valor;",
                                             'sintactico'))
                elif tokens[i + 1].tipo not in ['IDENTIFICADOR', 'ERROR_PALABRA_RESERVADA']:
                    self.errores.append(Error(token.linea, token.columna,
                                             f"Se esperaba un identificador después de '{token.valor}'",
                                             f"Ejemplo: {token.valor} miVariable = 10;",
                                             'sintactico'))
                else:
                    # Verificar que haya asignación o punto y coma
                    if i + 2 < len(tokens):
                        siguiente = tokens[i + 2]
                        if siguiente.valor not in ['=', ';', ',']:
                            # Buscar punto y coma en los próximos tokens
                            encontrado_punto_coma = False
                            for j in range(i + 2, min(i + 10, len(tokens))):
                                if tokens[j].valor == ';':
                                    encontrado_punto_coma = True
                                    break
                            
                            if not encontrado_punto_coma:
                                self.errores.append(Error(tokens[i + 1].linea, tokens[i + 1].columna,
                                                         f"Falta punto y coma ';' al final de la declaración",
                                                         f"Agregar ';' después de la declaración",
                                                         'sintactico'))
            
            i += 1

analizador_lexico = AnalizadorLexico()
analizador_sintactico = AnalizadorSintactico()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analizador Léxico y Sintáctico</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .toolbar {
            background: #f8fafc;
            padding: 20px;
            border-bottom: 2px solid #e2e8f0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
        }
        
        .btn-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        
        .btn-primary { background: #2563eb; color: white; }
        .btn-success { background: #059669; color: white; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-secondary { background: #6b7280; color: white; }
        .btn-warning { background: #f59e0b; color: white; }
        
        .status {
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 14px;
        }
        
        .status.success {
            background: #d1fae5;
            color: #065f46;
        }
        
        .status.error {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .status.warning {
            background: #fef3c7;
            color: #92400e;
        }
        
        .main-panel {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
        }
        
        .panel {
            background: #f9fafb;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }
        
        .panel-header {
            background: #374151;
            color: white;
            padding: 15px 20px;
            font-weight: bold;
            font-size: 18px;
        }
        
        .editor-container {
            background: #1e293b;
            display: flex;
            height: 500px;
        }
        
        .line-numbers {
            background: #334155;
            color: #94a3b8;
            padding: 15px 10px;
            text-align: right;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            user-select: none;
            min-width: 50px;
            overflow: hidden;
        }
        
        #codigo {
            flex: 1;
            background: #1e293b;
            color: #10b981;
            border: none;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: none;
            outline: none;
            line-height: 1.5;
        }
        
        .tabs {
            display: flex;
            background: #e5e7eb;
        }
        
        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border: none;
            background: transparent;
            font-weight: bold;
            transition: all 0.3s;
        }
        
        .tab.active {
            background: white;
            color: #2563eb;
        }
        
        .tab-content {
            display: none;
            padding: 20px;
            max-height: 500px;
            overflow-y: auto;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .error-item {
            background: white;
            border-left: 4px solid #dc2626;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .error-item.sintactico {
            border-left-color: #f59e0b;
        }
        
        .error-title {
            color: #991b1b;
            font-weight: bold;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .error-item.sintactico .error-title {
            color: #92400e;
        }
        
        .error-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            text-transform: uppercase;
        }
        
        .error-badge.lexico {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .error-badge.sintactico {
            background: #fef3c7;
            color: #92400e;
        }
        
        .error-message {
            color: #374151;
            margin-bottom: 5px;
            font-size: 14px;
        }
        
        .error-suggestion {
            color: #059669;
            font-style: italic;
            font-size: 13px;
            background: #d1fae5;
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
        }
        
        .token-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: white;
            margin-bottom: 5px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }
        
        .token-location {
            color: #6b7280;
            min-width: 60px;
        }
        
        .token-type {
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 11px;
            text-transform: uppercase;
            min-width: 150px;
            text-align: center;
        }
        
        .token-type.PALABRA_RESERVADA { background: #e9d5ff; color: #6b21a8; }
        .token-type.IDENTIFICADOR { background: #dbeafe; color: #1e40af; }
        .token-type.OPERADOR { background: #d1fae5; color: #065f46; }
        .token-type.DELIMITADOR { background: #fed7aa; color: #9a3412; }
        .token-type.LITERAL_ENTERO { background: #fecaca; color: #991b1b; }
        .token-type.LITERAL_FLOTANTE { background: #fecaca; color: #991b1b; }
        .token-type.LITERAL_CADENA { background: #fce7f3; color: #9f1239; }
        .token-type.COMENTARIO { background: #f3f4f6; color: #4b5563; }
        .token-type.ERROR_PALABRA_RESERVADA { background: #fee2e2; color: #dc2626; }
        
        .token-value {
            color: #374151;
            flex: 1;
        }
        
        .reference {
            background: #eff6ff;
            padding: 20px;
            border-radius: 8px;
            line-height: 1.8;
        }
        
        .reference h3 {
            color: #1e40af;
            margin-top: 15px;
            margin-bottom: 10px;
        }
        
        .reference h3:first-child {
            margin-top: 0;
        }
        
        .reference code {
            background: #dbeafe;
            padding: 2px 8px;
            border-radius: 4px;
            color: #1e3a8a;
        }
        
        .reference pre {
            background: #1e293b;
            color: #10b981;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            margin-top: 10px;
        }
        
        .success-message {
            background: #d1fae5;
            border-left: 4px solid #059669;
            padding: 15px;
            border-radius: 8px;
            color: #065f46;
            font-weight: bold;
        }
        
        .info-box {
            background: #dbeafe;
            border-left: 4px solid #2563eb;
            padding: 15px;
            border-radius: 8px;
            color: #1e40af;
            margin-bottom: 15px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .stat-value {
            font-size: 32px;
            font-weight: bold;
            color: #2563eb;
        }
        
        .stat-label {
            color: #6b7280;
            font-size: 14px;
            margin-top: 5px;
        }
        
        @media (max-width: 1024px) {
            .main-panel {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📝 Analizador Léxico y Sintáctico</h1>
            <p>Mini-Lenguaje de Programación en Español con Análisis Completo</p>
        </div>
        
        <div class="toolbar">
            <div class="btn-group">
                <button class="btn-secondary" onclick="cargarEjemplo()">
                    📄 Cargar Ejemplo
                </button>
                <button class="btn-warning" onclick="cargarEjemploConErrores()">
                    ⚠️ Ejemplo con Errores
                </button>
                <button class="btn-danger" onclick="limpiarEditor()">
                    🗑️ Limpiar
                </button>
                <button class="btn-success" onclick="descargarCodigo()">
                    💾 Guardar Código
                </button>
                <button class="btn-primary" onclick="descargarLog()">
                    📥 Descargar LOG
                </button>
            </div>
            <div id="status" class="status success">✓ Sin errores</div>
        </div>
        
        <div class="main-panel">
            <div class="panel">
                <div class="panel-header">✏️ Editor de Código</div>
                <div class="editor-container">
                    <div class="line-numbers" id="lineNumbers">1</div>
                    <textarea id="codigo" placeholder="// Escribe tu código aquí..." spellcheck="false"></textarea>
                </div>
            </div>
            
            <div class="panel">
                <div class="tabs">
                    <button class="tab active" onclick="cambiarTab('errores')">⚠️ Errores</button>
                    <button class="tab" onclick="cambiarTab('tokens')">🎯 Tokens</button>
                    <button class="tab" onclick="cambiarTab('estadisticas')">📊 Estadísticas</button>
                    <button class="tab" onclick="cambiarTab('referencia')">📚 Referencia</button>
                </div>
                
                <div id="errores" class="tab-content active">
                    <div class="success-message">✅ No se encontraron errores</div>
                </div>
                
                <div id="tokens" class="tab-content">
                    <p style="color: #6b7280;">Escribe código para ver los tokens...</p>
                </div>
                
                <div id="estadisticas" class="tab-content">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value" id="stat-tokens">0</div>
                            <div class="stat-label">Tokens</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="stat-errores">0</div>
                            <div class="stat-label">Errores</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="stat-lineas">0</div>
                            <div class="stat-label">Líneas</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="stat-palabras">0</div>
                            <div class="stat-label">Palabras Reservadas</div>
                        </div>
                    </div>
                    <div class="info-box">
                        <strong>ℹ️ Información del Análisis:</strong>
                        <div id="info-detalle" style="margin-top: 10px;"></div>
                    </div>
                </div>
                
                <div id="referencia" class="tab-content">
                    <div class="reference">
                        <h3>⚠️ Reglas Importantes:</h3>
                        <ul style="margin-left: 20px; line-height: 2;">
                            <li>Las palabras reservadas son <strong>sensibles a mayúsculas/minúsculas</strong></li>
                            <li>Usa <code>si</code> no <code>Si</code> o <code>SI</code></li>
                            <li>Todas las declaraciones deben terminar con <code>;</code></li>
                            <li>Los bloques deben estar entre <code>{ }</code></li>
                            <li>Las condiciones deben estar entre <code>( )</code></li>
                        </ul>
                        
                        <h3>📝 Palabras Reservadas:</h3>
                        <p><code>si</code> <code>sino</code> <code>mientras</code> <code>para</code> <code>entero</code> <code>flotante</code> <code>cadena</code> <code>retornar</code> <code>funcion</code> <code>verdadero</code> <code>falso</code> <code>imprimir</code> <code>leer</code></p>
                        
                        <h3>🔧 Operadores:</h3>
                        <p>
                            <strong>Aritméticos:</strong> <code>+</code> <code>-</code> <code>*</code> <code>/</code> <code>%</code><br>
                            <strong>Relacionales:</strong> <code>==</code> <code>!=</code> <code>&lt;</code> <code>&gt;</code> <code>&lt;=</code> <code>&gt;=</code><br>
                            <strong>Lógicos:</strong> <code>&&</code> <code>||</code> <code>!</code><br>
                            <strong>Asignación:</strong> <code>=</code>
                        </p>
                        
                        <h3>💬 Comentarios:</h3>
                        <p><code>// comentario de línea</code><br><code>/* comentario de bloque */</code></p>
                        
                        <h3>✅ Ejemplo Correcto:</h3>
                        <pre>// Declaración de variables
entero edad = 25;
flotante altura = 1.75;
cadena nombre = "Juan";

// Estructura condicional
si (edad >= 18) {
    imprimir("Mayor de edad");
} sino {
    imprimir("Menor de edad");
}

// Bucle mientras
mientras (edad < 30) {
    edad = edad + 1;
}</pre>
                        
                        <h3>❌ Errores Comunes:</h3>
                        <pre>// ❌ INCORRECTO
Si (x > 10)        // 'Si' debe ser 'si'
sipasa             // No existe, debe ser 'si'
entero x = 10      // Falta ';' al final
si x > 10 {        // Faltan paréntesis en condición
{                  // Llave sin cerrar</pre>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const codigoTextarea = document.getElementById('codigo');
        const lineNumbers = document.getElementById('lineNumbers');
        
        // Ejemplo correcto inicial
        const ejemploCorrecto = `// Programa de ejemplo en español
entero numero = 42;
flotante pi = 3.14;
cadena mensaje = "Hola Mundo";

si (numero > 10) {
    imprimir("Mayor que 10");
} sino {
    imprimir("Menor o igual");
}

mientras (numero > 0) {
    numero = numero - 1;
}`;

        // Ejemplo con errores comunes
        const ejemploConErrores = `// Este código tiene varios errores
entero edad = 25
flotante altura = 1.75;
cadena nombre = "Juan;

Si (edad >= 18) {
    imprimir("Mayor de edad")
} sino 
    imprimir("Menor de edad");
}

sipasa (altura > 1.50 {
    imprimir("Alto";
}

mientras (edad < 30 {
    edad = edad + 1
`;
        
        codigoTextarea.value = ejemploCorrecto;
        
        // Actualizar números de línea
        function actualizarNumeros() {
            const lineas = codigoTextarea.value.split('\n').length;
            lineNumbers.innerHTML = Array.from({length: lineas}, (_, i) => i + 1).join('\n');
        }
        
        // Analizar código
        function analizarCodigo() {
            const codigo = codigoTextarea.value;
            
            fetch('/analizar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({codigo: codigo})
            })
            .then(res => res.json())
            .then(data => {
                mostrarErrores(data.errores);
                mostrarTokens(data.tokens);
                mostrarEstadisticas(data.tokens, data.errores, codigo);
                actualizarEstado(data.errores);
            });
        }
        
        function mostrarErrores(errores) {
            const div = document.getElementById('errores');
            
            if (errores.length === 0) {
                div.innerHTML = '<div class="success-message">✅ No se encontraron errores léxicos ni sintácticos</div>';
            } else {
                // Separar errores por tipo
                const erroresLexicos = errores.filter(e => e.tipo === 'lexico');
                const erroresSintacticos = errores.filter(e => e.tipo === 'sintactico');
                
                let html = '';
                
                if (erroresLexicos.length > 0) {
                    html += '<div class="info-box">🔍 <strong>Errores Léxicos:</strong> Problemas con tokens individuales</div>';
                    html += erroresLexicos.map((e, i) => `
                        <div class="error-item">
                            <div class="error-title">
                                <span class="error-badge lexico">Léxico</span>
                                Error ${i + 1}: Línea ${e.linea}, Columna ${e.columna}
                            </div>
                            <div class="error-message">${e.mensaje}</div>
                            <div class="error-suggestion">💡 ${e.sugerencia}</div>
                        </div>
                    `).join('');
                }
                
                if (erroresSintacticos.length > 0) {
                    html += '<div class="info-box" style="background: #fef3c7; color: #92400e; border-left-color: #f59e0b;">⚙️ <strong>Errores Sintácticos:</strong> Problemas con la estructura del código</div>';
                    html += erroresSintacticos.map((e, i) => `
                        <div class="error-item sintactico">
                            <div class="error-title">
                                <span class="error-badge sintactico">Sintáctico</span>
                                Error ${i + 1}: Línea ${e.linea}, Columna ${e.columna}
                            </div>
                            <div class="error-message">${e.mensaje}</div>
                            <div class="error-suggestion">💡 ${e.sugerencia}</div>
                        </div>
                    `).join('');
                }
                
                div.innerHTML = html;
            }
        }
        
        function mostrarTokens(tokens) {
            const div = document.getElementById('tokens');
            
            if (tokens.length === 0) {
                div.innerHTML = '<p style="color: #6b7280;">No hay tokens para mostrar</p>';
            } else {
                let html = `<p style="font-weight: bold; margin-bottom: 15px;">Total de tokens identificados: ${tokens.length}</p>`;
                html += tokens.slice(0, 100).map(t => `
                    <div class="token-item">
                        <span class="token-location">${t.linea}:${t.columna}</span>
                        <span class="token-type ${t.tipo}">${t.tipo}</span>
                        <span class="token-value">${escapeHtml(t.valor)}</span>
                    </div>
                `).join('');
                
                if (tokens.length > 100) {
                    html += `<p style="text-align: center; color: #6b7280; margin-top: 10px;">... y ${tokens.length - 100} tokens más</p>`;
                }
                
                div.innerHTML = html;
            }
        }
        
        function mostrarEstadisticas(tokens, errores, codigo) {
            const lineas = codigo.split('\n').length;
            const palabrasReservadas = tokens.filter(t => t.tipo === 'PALABRA_RESERVADA').length;
            
            document.getElementById('stat-tokens').textContent = tokens.length;
            document.getElementById('stat-errores').textContent = errores.length;
            document.getElementById('stat-lineas').textContent = lineas;
            document.getElementById('stat-palabras').textContent = palabrasReservadas;
            
            // Información detallada
            const identificadores = tokens.filter(t => t.tipo === 'IDENTIFICADOR').length;
            const operadores = tokens.filter(t => t.tipo === 'OPERADOR').length;
            const literales = tokens.filter(t => t.tipo.includes('LITERAL')).length;
            const comentarios = tokens.filter(t => t.tipo === 'COMENTARIO').length;
            const erroresLexicos = errores.filter(e => e.tipo === 'lexico').length;
            const erroresSintacticos = errores.filter(e => e.tipo === 'sintactico').length;
            
            let info = `
                <strong>Distribución de Tokens:</strong><br>
                • Palabras Reservadas: ${palabrasReservadas}<br>
                • Identificadores: ${identificadores}<br>
                • Operadores/Delimitadores: ${operadores}<br>
                • Literales: ${literales}<br>
                • Comentarios: ${comentarios}<br><br>
                <strong>Análisis de Errores:</strong><br>
                • Errores Léxicos: ${erroresLexicos}<br>
                • Errores Sintácticos: ${erroresSintacticos}
            `;
            
            document.getElementById('info-detalle').innerHTML = info;
        }
        
        function actualizarEstado(errores) {
            const status = document.getElementById('status');
            const erroresLexicos = errores.filter(e => e.tipo === 'lexico').length;
            const erroresSintacticos = errores.filter(e => e.tipo === 'sintactico').length;
            
            if (errores.length === 0) {
                status.className = 'status success';
                status.textContent = '✓ Sin errores';
            } else if (erroresSintacticos > 0) {
                status.className = 'status warning';
                status.textContent = `⚠ ${erroresLexicos}L + ${erroresSintacticos}S error${errores.length > 1 ? 'es' : ''}`;
            } else {
                status.className = 'status error';
                status.textContent = `⚠ ${errores.length} error${errores.length > 1 ? 'es' : ''}`;
            }
        }
        
        function cambiarTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tab).classList.add('active');
        }
        
        function cargarEjemplo() {
            codigoTextarea.value = ejemploCorrecto;
            actualizarNumeros();
            analizarCodigo();
        }
        
        function cargarEjemploConErrores() {
            codigoTextarea.value = ejemploConErrores;
            actualizarNumeros();
            analizarCodigo();
        }
        
        function limpiarEditor() {
            if (confirm('¿Desea limpiar el editor?')) {
                codigoTextarea.value = '';
                actualizarNumeros();
                analizarCodigo();
            }
        }
        
        function descargarCodigo() {
            const blob = new Blob([codigoTextarea.value], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'codigo_' + Date.now() + '.txt';
            a.click();
        }
        
        function descargarLog() {
            fetch('/log', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({codigo: codigoTextarea.value})
            })
            .then(res => res.blob())
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'log_' + Date.now() + '.txt';
                a.click();
            });
        }
        
        function escapeHtml(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, m => map[m]);
        }
        
        // Event listeners
        codigoTextarea.addEventListener('input', () => {
            actualizarNumeros();
            analizarCodigo();
        });
        
        codigoTextarea.addEventListener('scroll', () => {
            lineNumbers.scrollTop = codigoTextarea.scrollTop;
        });
        
        // Análisis inicial
        actualizarNumeros();
        analizarCodigo();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analizar', methods=['POST'])
def analizar():
    data = request.get_json()
    codigo = data.get('codigo', '')
    
    # Análisis léxico
    tokens, errores_lexicos = analizador_lexico.analizar(codigo)
    
    # Análisis sintáctico
    errores_sintacticos = analizador_sintactico.analizar(tokens, codigo)
    
    # Combinar todos los errores
    todos_errores = errores_lexicos + errores_sintacticos
    
    return jsonify({
        'tokens': [t.to_dict() for t in tokens],
        'errores': [e.to_dict() for e in todos_errores]
    })

@app.route('/log', methods=['POST'])
def generar_log():
    data = request.get_json()
    codigo = data.get('codigo', '')
    
    tokens, errores_lexicos = analizador_lexico.analizar(codigo)
    errores_sintacticos = analizador_sintactico.analizar(tokens, codigo)
    
    log = analizador_lexico.generar_log(tokens, 'codigo.txt')
    
    # Agregar sección de errores al log
    if errores_lexicos or errores_sintacticos:
        log += "\n\n" + "=" * 60 + "\n"
        log += "=== ERRORES DETECTADOS ===\n"
        log += "=" * 60 + "\n\n"
        
        if errores_lexicos:
            log += "ERRORES LÉXICOS:\n"
            log += "-" * 40 + "\n"
            for i, error in enumerate(errores_lexicos, 1):
                log += f"\nError {i}:\n"
                log += f"  Línea: {error.linea}, Columna: {error.columna}\n"
                log += f"  Mensaje: {error.mensaje}\n"
                log += f"  Sugerencia: {error.sugerencia}\n"
        
        if errores_sintacticos:
            log += "\n\nERRORES SINTÁCTICOS:\n"
            log += "-" * 40 + "\n"
            for i, error in enumerate(errores_sintacticos, 1):
                log += f"\nError {i}:\n"
                log += f"  Línea: {error.linea}, Columna: {error.columna}\n"
                log += f"  Mensaje: {error.mensaje}\n"
                log += f"  Sugerencia: {error.sugerencia}\n"
    
    return send_file(
        io.BytesIO(log.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    )

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ANALIZADOR LÉXICO Y SINTÁCTICO - SERVIDOR WEB")
    print("="*60)
    print("\n📡 Servidor iniciado correctamente")
    print("🌐 Abre tu navegador en: http://localhost:5000")
    print("\n✨ Características:")
    print("   • Análisis léxico en tiempo real")
    print("   • Detección de errores sintácticos")
    print("   • Verificación de palabras reservadas (case-sensitive)")
    print("   • Detección de paréntesis y llaves sin cerrar")
    print("   • Sugerencias de corrección")
    print("\n⌨️  Presiona Ctrl+C para detener el servidor\n")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)