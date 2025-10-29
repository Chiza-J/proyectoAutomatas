import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from typing import List, Dict, Tuple
import re

class Token:
    def __init__(self, tipo, valor, linea, columna):
        self.tipo = tipo
        self.valor = valor
        self.linea = linea
        self.columna = columna
    
    def __repr__(self):
        return f"Token({self.tipo}, '{self.valor}', L{self.linea}:C{self.columna})"

class Error:
    def __init__(self, linea, columna, mensaje, sugerencia, tipo='lexico'):
        self.linea = linea
        self.columna = columna
        self.mensaje = mensaje
        self.sugerencia = sugerencia
        self.tipo = tipo
    
    def __repr__(self):
        return f"Error({self.tipo}, L{self.linea}:C{self.columna}, {self.mensaje})"

class AnalizadorLexico:
    def __init__(self):
        self.palabras_reservadas = {
            'si', 'sino', 'mientras', 'para', 'entero', 'flotante', 
            'cadena', 'retornar', 'funcion', 'verdadero', 'falso', 
            'imprimir', 'leer'
        }
        
        self.sugerencias_comunes = {
            'if': 'si', 'else': 'sino', 'while': 'mientras', 'for': 'para',
            'int': 'entero', 'float': 'flotante', 'string': 'cadena',
            'return': 'retornar', 'function': 'funcion', 'true': 'verdadero',
            'false': 'falso', 'print': 'imprimir', 'read': 'leer',
            'sipasa': 'si', 'Si': 'si', 'Sino': 'sino', 'Mientras': 'mientras'
        }
        
        self.operadores_dobles = ['==', '!=', '<=', '>=', '&&', '||']
        self.operadores_simples = ['+', '-', '*', '/', '%', '<', '>', '!', '=']
        self.delimitadores = ['(', ')', '{', '}', ';', ',']
    
    def analizar(self, codigo):
        """Analiza el código completo"""
        tokens = []
        errores = []
        
        # Pre-procesar comentarios de bloque multilínea
        codigo_procesado, comentarios_bloque = self.extraer_comentarios_bloque(codigo)
        
        # Agregar tokens de comentarios
        for comentario in comentarios_bloque:
            tokens.append(comentario)
        
        lineas = codigo_procesado.split('\n')
        
        for num_linea, linea in enumerate(lineas, 1):
            pos = 0
            
            while pos < len(linea):
                # Saltar espacios
                if linea[pos].isspace():
                    pos += 1
                    continue
                
                # Comentarios de línea //
                if pos < len(linea) - 1 and linea[pos:pos+2] == '//':
                    tokens.append(Token('COMENTARIO', linea[pos:], num_linea, pos + 1))
                    break
                
                # Cadenas de texto
                if linea[pos] in ['"', "'"]:
                    resultado = self.procesar_cadena(linea, pos, num_linea)
                    if resultado['error']:
                        errores.append(resultado['error'])
                    if resultado['token']:
                        tokens.append(resultado['token'])
                    pos = resultado['nueva_pos']
                    continue
                
                # Números
                if linea[pos].isdigit():
                    resultado = self.procesar_numero(linea, pos, num_linea)
                    if resultado['error']:
                        errores.append(resultado['error'])
                    if resultado['token']:
                        tokens.append(resultado['token'])
                    pos = resultado['nueva_pos']
                    continue
                
                # Detectar secuencias de = repetidas (como ========)
                if linea[pos] == '=':
                    count_equals = 0
                    start_pos = pos
                    while pos < len(linea) and linea[pos] == '=':
                        count_equals += 1
                        pos += 1
                    
                    if count_equals == 1:
                        # Un solo = es asignación
                        tokens.append(Token('OPERADOR', '=', num_linea, start_pos + 1))
                    elif count_equals == 2:
                        # == es comparación válida
                        tokens.append(Token('OPERADOR', '==', num_linea, start_pos + 1))
                    else:
                        # Más de 2 = es error
                        errores.append(Error(num_linea, start_pos + 1,
                                           f"Secuencia inválida de operadores '=': {'=' * count_equals}",
                                           "Usar '=' para asignación o '==' para comparación"))
                    continue
                
                # Detectar <> (operador inválido común)
                if pos < len(linea) - 1 and linea[pos:pos+2] == '<>':
                    errores.append(Error(num_linea, pos + 1,
                                       f"Operador no reconocido: '<>'",
                                       "Usar '!=' para comparación de diferente"))
                    pos += 2
                    continue
                
                # Verificar operadores inválidos
                if pos < len(linea) - 1:
                    dos_chars = linea[pos:pos+2]
                    
                    # Detectar >> y <<
                    if dos_chars in ['>>', '<<']:
                        errores.append(Error(num_linea, pos + 1,
                                           f"Operador no reconocido: '{dos_chars}'",
                                           "Los operadores válidos son: +, -, *, /, %, ==, !=, <, >, <=, >=, &&, ||, !"))
                        pos += 2
                        continue
                    
                    # Detectar operadores repetidos inválidos como &&&& o ||||
                    if pos < len(linea) - 3:
                        cuatro_chars = linea[pos:pos+4]
                        if cuatro_chars in ['&&&&', '||||']:
                            errores.append(Error(num_linea, pos + 1,
                                               f"Operador repetido inválido: '{cuatro_chars}'",
                                               "Usar solo '&&' o '||' (dos caracteres)"))
                            pos += 4
                            continue
                    
                    # Detectar &&& o |||
                    tres_chars = linea[pos:pos+3]
                    if tres_chars in ['&&&', '|||']:
                        errores.append(Error(num_linea, pos + 1,
                                           f"Operador inválido: '{tres_chars}'",
                                           "Usar solo '&&' o '||' (dos caracteres)"))
                        pos += 3
                        continue
                    
                    # Operadores dobles válidos
                    if dos_chars in self.operadores_dobles:
                        tokens.append(Token('OPERADOR', dos_chars, num_linea, pos + 1))
                        pos += 2
                        continue
                
                # Detectar & o | solos (inválidos)
                if linea[pos] in ['&', '|']:
                    errores.append(Error(num_linea, pos + 1,
                                       f"Operador incompleto: '{linea[pos]}'",
                                       f"Usar '{linea[pos]}{linea[pos]}' para operador lógico"))
                    pos += 1
                    continue
                
                # Operadores simples (ahora sin =, ya fue procesado antes)
                if linea[pos] in ['+', '-', '*', '/', '%', '<', '>', '!']:
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
                    resultado = self.procesar_identificador(linea, pos, num_linea)
                    if resultado['error']:
                        errores.append(resultado['error'])
                    tokens.append(resultado['token'])
                    pos = resultado['nueva_pos']
                    continue
                
                # Caracter no reconocido
                errores.append(Error(num_linea, pos + 1,
                                   f"Caracter no reconocido: '{linea[pos]}'",
                                   "Verificar si es un operador o símbolo válido"))
                pos += 1
        
        return tokens, errores
    
    def extraer_comentarios_bloque(self, codigo):
        """Extrae comentarios de bloque /* */ multilínea"""
        comentarios = []
        codigo_limpio = ""
        pos = 0
        linea_actual = 1
        columna_actual = 1
        
        while pos < len(codigo):
            if pos < len(codigo) - 1 and codigo[pos:pos+2] == '/*':
                inicio_linea = linea_actual
                inicio_columna = columna_actual
                comentario_texto = '/*'
                pos += 2
                columna_actual += 2
                
                encontrado_cierre = False
                while pos < len(codigo):
                    if pos < len(codigo) - 1 and codigo[pos:pos+2] == '*/':
                        comentario_texto += '*/'
                        pos += 2
                        columna_actual += 2
                        encontrado_cierre = True
                        break
                    else:
                        if codigo[pos] == '\n':
                            linea_actual += 1
                            columna_actual = 1
                        else:
                            columna_actual += 1
                        comentario_texto += codigo[pos]
                        pos += 1
                
                comentarios.append(Token('COMENTARIO', comentario_texto, inicio_linea, inicio_columna))
                codigo_limpio += ' ' * len(comentario_texto)
            else:
                codigo_limpio += codigo[pos]
                if codigo[pos] == '\n':
                    linea_actual += 1
                    columna_actual = 1
                else:
                    columna_actual += 1
                pos += 1
        
        return codigo_limpio, comentarios
    
    def procesar_cadena(self, linea, pos, num_linea):
        """Procesa una cadena de texto"""
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
            token = Token('LITERAL_CADENA', linea[pos:fin_cadena+1], num_linea, pos + 1)
            return {'token': token, 'error': None, 'nueva_pos': fin_cadena + 1}
        else:
            error = Error(num_linea, pos + 1,
                         f"Cadena sin cerrar",
                         f"Agregar {comilla} al final de la cadena")
            return {'token': None, 'error': error, 'nueva_pos': len(linea)}
    
    def procesar_numero(self, linea, pos, num_linea):
        """Procesa un número entero o flotante"""
        inicio_num = pos
        numero = ''
        tiene_decimal = False
        
        while pos < len(linea) and (linea[pos].isdigit() or linea[pos] == '.'):
            if linea[pos] == '.':
                if tiene_decimal:
                    error = Error(num_linea, inicio_num + 1,
                                 f"Número con múltiples puntos decimales: {numero + linea[pos]}",
                                 "Usar solo un punto decimal")
                    return {'token': None, 'error': error, 'nueva_pos': pos + 1}
                tiene_decimal = True
            numero += linea[pos]
            pos += 1
        
        if pos < len(linea) and (linea[pos].isalpha() or linea[pos] == '_'):
            invalido = numero
            while pos < len(linea) and (linea[pos].isalnum() or linea[pos] == '_'):
                invalido += linea[pos]
                pos += 1
            error = Error(num_linea, inicio_num + 1,
                         f"Identificador inválido: '{invalido}'",
                         "Los identificadores no pueden comenzar con números")
            return {'token': None, 'error': error, 'nueva_pos': pos}
        else:
            tipo = 'LITERAL_FLOTANTE' if tiene_decimal else 'LITERAL_ENTERO'
            token = Token(tipo, numero, num_linea, inicio_num + 1)
            return {'token': token, 'error': None, 'nueva_pos': pos}
    
    def procesar_identificador(self, linea, pos, num_linea):
        """Procesa un identificador o palabra reservada"""
        inicio_id = pos
        identificador = ''
        
        while pos < len(linea) and (linea[pos].isalnum() or linea[pos] == '_'):
            identificador += linea[pos]
            pos += 1
        
        if identificador in self.palabras_reservadas:
            token = Token('PALABRA_RESERVADA', identificador, num_linea, inicio_id + 1)
            return {'token': token, 'error': None, 'nueva_pos': pos}
        else:
            sugerencia = None
            
            if identificador in self.sugerencias_comunes or identificador.lower() in self.sugerencias_comunes:
                sugerencia = self.sugerir_palabra_reservada(identificador)
            elif len(identificador) >= 3:
                sugerencia = self.sugerir_palabra_reservada(identificador)
            
            if sugerencia:
                error = Error(num_linea, inicio_id + 1,
                             f"Palabra reservada mal escrita: '{identificador}'",
                             f"¿Quisiste decir '{sugerencia}'?")
                token = Token('ERROR_PALABRA', identificador, num_linea, inicio_id + 1)
                return {'token': token, 'error': error, 'nueva_pos': pos}
            else:
                token = Token('IDENTIFICADOR', identificador, num_linea, inicio_id + 1)
                return {'token': token, 'error': None, 'nueva_pos': pos}
    
    def sugerir_palabra_reservada(self, palabra):
        """Sugiere la palabra reservada correcta"""
        if palabra in self.sugerencias_comunes:
            return self.sugerencias_comunes[palabra]
        
        palabra_lower = palabra.lower()
        if palabra_lower in self.sugerencias_comunes:
            return self.sugerencias_comunes[palabra_lower]
        
        if len(palabra) <= 2:
            return None
        
        for reservada in self.palabras_reservadas:
            if self.es_similar(palabra_lower, reservada):
                return reservada
        
        return None
    
    def es_similar(self, palabra1, palabra2):
        """Verifica si dos palabras son similares"""
        if abs(len(palabra1) - len(palabra2)) > 2:
            return False
        
        if len(palabra1) <= 2 or len(palabra2) <= 2:
            return False
        
        diferencias = 0
        for i in range(min(len(palabra1), len(palabra2))):
            if palabra1[i] != palabra2[i]:
                diferencias += 1
            if diferencias > 2:
                return False
        
        diferencias += abs(len(palabra1) - len(palabra2))
        return diferencias <= 2

class AnalizadorSintactico:
    def analizar(self, tokens, codigo):
        """Análisis sintáctico EXTREMADAMENTE ESTRICTO como un compilador"""
        errores = []
        
        # Verificar comentarios de bloque
        errores.extend(self.verificar_comentarios_bloque(tokens))
        
        # Verificar delimitadores PRIMERO (más importante)
        errores.extend(self.verificar_delimitadores_estricto(tokens))
        
        # Verificar orden correcto de tokens en expresiones
        errores.extend(self.verificar_secuencia_tokens(tokens))
        
        # Verificar estructuras de control
        errores.extend(self.verificar_estructuras(tokens))
        
        # Verificar declaraciones
        errores.extend(self.verificar_declaraciones_estricto(tokens))
        
        # Verificar llamadas a funciones
        errores.extend(self.verificar_llamadas_funciones(tokens))
        
        # Verificar que los operadores estén bien ubicados
        errores.extend(self.verificar_operadores_contexto(tokens))
        
        return errores
    
    def verificar_secuencia_tokens(self, tokens):
        """Verifica que la secuencia de tokens sea válida"""
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        
        for i in range(len(tokens_sin_comentarios) - 1):
            token_actual = tokens_sin_comentarios[i]
            token_siguiente = tokens_sin_comentarios[i + 1]
            
            # Un operador NO puede estar seguido de un delimitador de cierre ) o }
            if token_actual.tipo == 'OPERADOR' and token_actual.valor not in ['!', '-', '+']:
                if token_siguiente.valor in [')', '}']:
                    errores.append(Error(token_actual.linea, token_actual.columna,
                                       f"Operador '{token_actual.valor}' seguido de '{token_siguiente.valor}' es inválido",
                                       f"Un operador debe estar seguido de un valor, no de '{token_siguiente.valor}'",
                                       'sintactico'))
                # Operador seguido de operador (excepto ! - +)
                elif token_siguiente.tipo == 'OPERADOR' and token_siguiente.valor not in ['!', '-', '+']:
                    errores.append(Error(token_actual.linea, token_actual.columna,
                                       f"Dos operadores consecutivos: '{token_actual.valor}' '{token_siguiente.valor}'",
                                       "Los operadores deben estar separados por valores",
                                       'sintactico'))
            
            # Un delimitador de apertura ( debe estar seguido de algo válido
            if token_actual.valor == '(':
                # ( no puede estar seguido de operadores binarios
                if token_siguiente.tipo == 'OPERADOR' and token_siguiente.valor not in ['!', '-', '+']:
                    errores.append(Error(token_siguiente.linea, token_siguiente.columna,
                                       f"Operador '{token_siguiente.valor}' después de '(' es inválido",
                                       "Después de '(' debe ir un valor, identificador o expresión",
                                       'sintactico'))
        
        return errores
    
    def verificar_operadores_contexto(self, tokens):
        """Verifica que los operadores estén en contextos válidos"""
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        
        for i, token in enumerate(tokens_sin_comentarios):
            if token.tipo == 'OPERADOR':
                # Verificar operadores relacionales dentro de llamadas a funciones
                if token.valor in ['<=', '>=', '==', '!=', '<', '>']:
                    # Buscar si estamos dentro de una llamada a función (entre paréntesis de función)
                    if self.esta_en_llamada_funcion(tokens_sin_comentarios, i):
                        errores.append(Error(token.linea, token.columna,
                                           f"Operador relacional '{token.valor}' dentro de llamada a función",
                                           "Los operadores relacionales no van dentro de llamadas a función como imprimir()",
                                           'sintactico'))
        
        return errores
    
    def esta_en_llamada_funcion(self, tokens, pos):
        """Verifica si la posición está dentro de una llamada a función"""
        # Buscar hacia atrás hasta encontrar un paréntesis de apertura
        nivel = 0
        for i in range(pos - 1, -1, -1):
            if tokens[i].valor == ')':
                nivel += 1
            elif tokens[i].valor == '(':
                if nivel == 0:
                    # Verificar si antes del ( hay una función
                    if i > 0 and tokens[i - 1].tipo == 'PALABRA_RESERVADA':
                        if tokens[i - 1].valor in ['imprimir', 'leer']:
                            return True
                    return False
                else:
                    nivel -= 1
        return False
    
    def verificar_delimitadores_estricto(self, tokens):
        """Verifica delimitadores con análisis ESTRICTO de orden correcto"""
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        
        pila = []  # Pila para rastrear delimitadores abiertos
        
        for i, token in enumerate(tokens_sin_comentarios):
            if token.tipo == 'DELIMITADOR':
                if token.valor == '(':
                    pila.append({'tipo': 'parentesis', 'token': token, 'indice': i})
                
                elif token.valor == ')':
                    if not pila:
                        errores.append(Error(token.linea, token.columna,
                                           "Paréntesis ')' sin abrir",
                                           "Agregar '(' antes o eliminar ')'", 'sintactico'))
                    else:
                        ultimo = pila[-1]
                        if ultimo['tipo'] == 'parentesis':
                            pila.pop()
                        elif ultimo['tipo'] == 'llave':
                            errores.append(Error(token.linea, token.columna,
                                                "Orden incorrecto de delimitadores: se esperaba '}' pero se encontró ')'",
                                                f"Cerrar la llave abierta en línea {ultimo['token'].linea} antes de cerrar paréntesis",
                                                'sintactico'))
                
                elif token.valor == '{':
                    # Verificar que antes de { haya una condición válida con )
                    if i > 0:
                        token_anterior = tokens_sin_comentarios[i - 1]
                        # Debe haber un ) antes del {
                        if token_anterior.valor != ')':
                            # Buscar hacia atrás si hay un ) cercano
                            encontrado_parentesis = False
                            for j in range(i - 1, max(0, i - 5), -1):
                                if tokens_sin_comentarios[j].valor == ')':
                                    encontrado_parentesis = True
                                    break
                            
                            if not encontrado_parentesis:
                                errores.append(Error(token.linea, token.columna,
                                                   "Llave '{' sin condición válida antes",
                                                   "Las estructuras deben tener: palabra_reservada (condicion) { ... }",
                                                   'sintactico'))
                    
                    pila.append({'tipo': 'llave', 'token': token, 'indice': i})
                
                elif token.valor == '}':
                    if not pila:
                        errores.append(Error(token.linea, token.columna,
                                           "Llave '}' sin abrir",
                                           "Agregar '{' antes o eliminar '}'", 'sintactico'))
                    else:
                        ultimo = pila[-1]
                        if ultimo['tipo'] == 'llave':
                            pila.pop()
                        elif ultimo['tipo'] == 'parentesis':
                            errores.append(Error(token.linea, token.columna,
                                                "Orden incorrecto de delimitadores: se esperaba ')' pero se encontró '}'",
                                                f"Cerrar el paréntesis abierto en línea {ultimo['token'].linea} antes de cerrar llaves",
                                                'sintactico'))
        
        # Verificar delimitadores sin cerrar
        for item in pila:
            if item['tipo'] == 'parentesis':
                errores.append(Error(item['token'].linea, item['token'].columna,
                                   "Paréntesis '(' sin cerrar",
                                   "Agregar ')' al final", 'sintactico'))
            elif item['tipo'] == 'llave':
                errores.append(Error(item['token'].linea, item['token'].columna,
                                   "Llave '{' sin cerrar",
                                   "Agregar '}' al final", 'sintactico'))
        
        return errores
    
    def verificar_comentarios_bloque(self, tokens):
        """Verifica que los comentarios de bloque estén cerrados"""
        errores = []
        comentarios_bloque = [t for t in tokens if t.tipo == 'COMENTARIO' and t.valor.startswith('/*')]
        
        for comentario in comentarios_bloque:
            if not comentario.valor.endswith('*/'):
                errores.append(Error(comentario.linea, comentario.columna,
                                   "Comentario de bloque sin cerrar",
                                   "Agregar */ al final del comentario", 'sintactico'))
        
        return errores
    
    def verificar_estructuras(self, tokens):
        """Verifica estructuras de control"""
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        i = 0
        
        while i < len(tokens_sin_comentarios):
            token = tokens_sin_comentarios[i]
            
            if token.tipo == 'PALABRA_RESERVADA':
                if token.valor in ['si', 'mientras', 'para']:
                    # Debe seguir INMEDIATAMENTE un (
                    if i + 1 >= len(tokens_sin_comentarios):
                        errores.append(Error(token.linea, token.columna,
                                           f"Falta '(' después de '{token.valor}'",
                                           f"Usar: {token.valor} (condicion) {{ ... }}", 'sintactico'))
                    elif tokens_sin_comentarios[i + 1].valor != '(':
                        errores.append(Error(token.linea, token.columna,
                                           f"Se esperaba '(' después de '{token.valor}' pero se encontró '{tokens_sin_comentarios[i + 1].valor}'",
                                           f"Usar: {token.valor} (condicion) {{ ... }}", 'sintactico'))
            i += 1
        
        return errores
    
    def verificar_declaraciones_estricto(self, tokens):
        """Verificación ESTRICTA de declaraciones"""
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        i = 0
        
        while i < len(tokens_sin_comentarios):
            token = tokens_sin_comentarios[i]
            
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in ['entero', 'flotante', 'cadena']:
                if i + 1 >= len(tokens_sin_comentarios):
                    errores.append(Error(token.linea, token.columna,
                                       f"Declaración incompleta después de '{token.valor}'",
                                       f"Usar: {token.valor} nombre = valor;", 'sintactico'))
                elif tokens_sin_comentarios[i + 1].tipo not in ['IDENTIFICADOR', 'ERROR_PALABRA']:
                    errores.append(Error(token.linea, token.columna,
                                       f"Se esperaba identificador después de '{token.valor}'",
                                       f"Ejemplo: {token.valor} miVariable;", 'sintactico'))
                else:
                    # Buscar punto y coma
                    encontrado_puntocoma = False
                    for j in range(i + 2, min(i + 20, len(tokens_sin_comentarios))):
                        if tokens_sin_comentarios[j].valor == ';':
                            encontrado_puntocoma = True
                            break
                        if tokens_sin_comentarios[j].tipo == 'PALABRA_RESERVADA':
                            break
                        if tokens_sin_comentarios[j].valor == '}':
                            break
                    
                    if not encontrado_puntocoma:
                        errores.append(Error(tokens_sin_comentarios[i + 1].linea, 
                                           tokens_sin_comentarios[i + 1].columna,
                                           f"Falta ';' al final de la declaración",
                                           "Agregar punto y coma al final de la línea", 'sintactico'))
            i += 1
        
        return errores
    
    def verificar_llamadas_funciones(self, tokens):
        """Verifica llamadas a funciones con análisis ESTRICTO"""
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        i = 0
        
        while i < len(tokens_sin_comentarios):
            token = tokens_sin_comentarios[i]
            
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in ['imprimir', 'leer']:
                # Verificar que siga INMEDIATAMENTE un (
                if i + 1 >= len(tokens_sin_comentarios):
                    errores.append(Error(token.linea, token.columna,
                                       f"Falta '(' después de '{token.valor}'",
                                       f"La sintaxis correcta es: {token.valor}(...);", 'sintactico'))
                    i += 1
                    continue
                
                if tokens_sin_comentarios[i + 1].valor != '(':
                    errores.append(Error(token.linea, token.columna,
                                       f"Se esperaba '(' después de '{token.valor}' pero se encontró '{tokens_sin_comentarios[i + 1].valor}'",
                                       f"La sintaxis correcta es: {token.valor}(...);", 'sintactico'))
                    i += 1
                    continue
                
                # Buscar el paréntesis de cierre
                j = i + 2  # Empezar después del (
                nivel_parentesis = 1
                pos_cierre = -1
                
                while j < len(tokens_sin_comentarios) and nivel_parentesis > 0:
                    if tokens_sin_comentarios[j].valor == '(':
                        nivel_parentesis += 1
                    elif tokens_sin_comentarios[j].valor == ')':
                        nivel_parentesis -= 1
                        if nivel_parentesis == 0:
                            pos_cierre = j
                            break
                    elif tokens_sin_comentarios[j].valor in ['}', ';'] and nivel_parentesis > 0:
                        errores.append(Error(tokens_sin_comentarios[i + 1].linea, 
                                           tokens_sin_comentarios[i + 1].columna,
                                           f"Paréntesis '(' de '{token.valor}' sin cerrar",
                                           "Agregar ')' antes del delimitador", 'sintactico'))
                        break
                    j += 1
                
                # Si no encontramos el cierre
                if pos_cierre == -1:
                    errores.append(Error(tokens_sin_comentarios[i + 1].linea, 
                                       tokens_sin_comentarios[i + 1].columna,
                                       f"Paréntesis '(' de '{token.valor}' sin cerrar",
                                       "Agregar ')' al final de la llamada", 'sintactico'))
                
                # Si encontramos el cierre, verificar punto y coma
                if pos_cierre != -1:
                    if pos_cierre + 1 < len(tokens_sin_comentarios):
                        siguiente = tokens_sin_comentarios[pos_cierre + 1]
                        if siguiente.valor != ';':
                            errores.append(Error(tokens_sin_comentarios[pos_cierre].linea, 
                                               tokens_sin_comentarios[pos_cierre].columna,
                                               f"Falta ';' después de '{token.valor}(...)'",
                                               "Agregar punto y coma al final de la llamada", 'sintactico'))
                    else:
                        errores.append(Error(tokens_sin_comentarios[pos_cierre].linea, 
                                           tokens_sin_comentarios[pos_cierre].columna,
                                           f"Falta ';' después de '{token.valor}(...)'",
                                           "Agregar punto y coma al final de la llamada", 'sintactico'))
            
            i += 1
        
        return errores

class InterfazAnalizador:
    def __init__(self, root):
        self.root = root
        self.root.title("Analizador Léxico y Sintáctico - Mini-Lenguaje")
        self.root.geometry("1400x900")
        
        self.analizador_lexico = AnalizadorLexico()
        self.analizador_sintactico = AnalizadorSintactico()
        
        self.nombre_archivo = "codigo.txt"
        self.tokens = []
        self.errores = []
        
        self.crear_interfaz()
        self.cargar_ejemplo_correcto()
    
    def crear_interfaz(self):
        # Header
        header = tk.Frame(self.root, bg='#2563eb', height=100)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(header, text="📝 Analizador Léxico y Sintáctico", 
                font=('Arial', 24, 'bold'), bg='#2563eb', fg='white').pack(pady=10)
        tk.Label(header, text="Mini-Lenguaje de Programación en Español", 
                font=('Arial', 12), bg='#2563eb', fg='#bfdbfe').pack()
        
        # Toolbar
        toolbar = tk.Frame(self.root, bg='#f1f5f9', height=60)
        toolbar.pack(fill='x')
        toolbar.pack_propagate(False)
        
        btn_frame = tk.Frame(toolbar, bg='#f1f5f9')
        btn_frame.pack(side='left', padx=10, pady=10)
        
        tk.Button(btn_frame, text="📁 Cargar Archivo", command=self.cargar_archivo,
                 bg='#475569', fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="📄 Ejemplo Correcto", command=self.cargar_ejemplo_correcto,
                 bg='#059669', fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="⚠️ Ejemplo con Errores", command=self.cargar_ejemplo_errores,
                 bg='#f59e0b', fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="💾 Guardar", command=self.guardar_codigo,
                 bg='#0284c7', fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="📥 LOG", command=self.descargar_log,
                 bg='#7c3aed', fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="🗑️ Limpiar", command=self.limpiar_editor,
                 bg='#dc2626', fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        # Estado
        self.label_estado = tk.Label(toolbar, text="✓ Sin errores", 
                                     font=('Arial', 12, 'bold'), bg='#f1f5f9', fg='#059669')
        self.label_estado.pack(side='right', padx=20)
        
        # Panel principal
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Panel izquierdo - Editor
        left_panel = tk.Frame(main_frame, bg='white', relief='solid', bd=1)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        tk.Label(left_panel, text="✏️ Editor de Código", 
                font=('Arial', 14, 'bold'), bg='white', pady=10).pack()
        
        editor_frame = tk.Frame(left_panel, bg='#1e293b')
        editor_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.numeros_linea = tk.Text(editor_frame, width=4, bg='#334155', fg='#94a3b8',
                                     font=('Consolas', 11), state='disabled', padx=5,
                                     takefocus=0, cursor='arrow')
        self.numeros_linea.pack(side='left', fill='y')
        
        scrollbar = tk.Scrollbar(editor_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.editor_texto = tk.Text(editor_frame, wrap='none',
                                   bg='#1e293b', fg='#10b981',
                                   font=('Consolas', 11), 
                                   insertbackground='white',
                                   yscrollcommand=scrollbar.set)
        self.editor_texto.pack(side='left', fill='both', expand=True)
        
        scrollbar.config(command=self.scroll_ambos)
        
        self.editor_texto.bind('<KeyRelease>', lambda e: self.analizar_en_tiempo_real())
        self.editor_texto.bind('<MouseWheel>', self.on_mousewheel)
        self.editor_texto.bind('<Button-4>', self.on_mousewheel)
        self.editor_texto.bind('<Button-5>', self.on_mousewheel)
        
        # Panel derecho
        right_panel = tk.Frame(main_frame, bg='white', relief='solid', bd=1)
        right_panel.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        tk.Label(right_panel, text="📊 Análisis", 
                font=('Arial', 14, 'bold'), bg='white', pady=10).pack()
        
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab Errores
        tab_errores = tk.Frame(self.notebook, bg='#fef2f2')
        self.notebook.add(tab_errores, text='⚠️ Errores')
        
        self.texto_errores = scrolledtext.ScrolledText(tab_errores, wrap='word',
                                                       bg='#fef2f2', font=('Arial', 10))
        self.texto_errores.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab Tokens
        tab_tokens = tk.Frame(self.notebook, bg='#f9fafb')
        self.notebook.add(tab_tokens, text='🎯 Tokens')
        
        self.texto_tokens = scrolledtext.ScrolledText(tab_tokens, wrap='word',
                                                      bg='#f9fafb', font=('Consolas', 9))
        self.texto_tokens.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab Referencia
        tab_ref = tk.Frame(self.notebook, bg='#eff6ff')
        self.notebook.add(tab_ref, text='📚 Referencia')
        
        texto_ref = scrolledtext.ScrolledText(tab_ref, wrap='word', bg='#eff6ff',
                                              font=('Arial', 10))
        texto_ref.pack(fill='both', expand=True, padx=10, pady=10)
        
        referencia = """📚 REFERENCIA DEL MINI-LENGUAJE

⚠️ REGLAS ESTRICTAS:
• Las palabras reservadas son SENSIBLES a mayúsculas
• Usa 'si' NO 'Si' o 'SI'
• TODAS las declaraciones DEBEN terminar con ';'
• TODAS las llamadas a funciones DEBEN terminar con ';'
• Los bloques usan llaves { }
• Las condiciones usan paréntesis ( )
• Los comentarios de bloque /* */ pueden ser multilínea

📝 PALABRAS RESERVADAS:
si, sino, mientras, para, entero, flotante, cadena,
retornar, funcion, verdadero, falso, imprimir, leer

🔧 OPERADORES VÁLIDOS:
Aritméticos: +  -  *  /  %
Relacionales: ==  !=  <  >  <=  >=
Lógicos: &&  ||  !
Asignación: =

❌ OPERADORES INVÁLIDOS:
>> << (no existen en este lenguaje)
& | (usar && o || para lógicos)
&&& &&&& (usar solo &&)
||| |||| (usar solo ||)

💬 COMENTARIOS:
// Comentario de línea
/* Comentario de bloque 
   puede estar en múltiples líneas */

✅ EJEMPLO CORRECTO:

entero edad = 25;
si (edad >= 18) {
    imprimir("Mayor de edad");
} sino {
    imprimir("Menor de edad");
}

/* Comentario multilínea correcto */
mientras (edad < 30) {
    edad = edad + 1;
}

❌ EJEMPLO INCORRECTO:

entero edad = 25          // ❌ Falta ;
si (edad >= 18) {
    imprimir("Mayor")     // ❌ Falta ; después de imprimir
}
si (x > 5 &&&& y < 30)    // ❌ &&&& es inválido (usar &&)
entero x = 5 >> 2;        // ❌ >> no existe
"""
        texto_ref.insert('1.0', referencia)
        texto_ref.config(state='disabled')
    
    def scroll_ambos(self, *args):
        self.editor_texto.yview(*args)
        self.numeros_linea.yview(*args)
    
    def on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.editor_texto.yview_scroll(1, "units")
            self.numeros_linea.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.editor_texto.yview_scroll(-1, "units")
            self.numeros_linea.yview_scroll(-1, "units")
        return "break"
    
    def actualizar_numeros_linea(self):
        texto = self.editor_texto.get('1.0', 'end-1c')
        num_lineas = texto.count('\n') + 1
        
        posicion_scroll = self.editor_texto.yview()
        
        self.numeros_linea.config(state='normal')
        self.numeros_linea.delete('1.0', 'end')
        numeros = '\n'.join(str(i) for i in range(1, num_lineas + 1))
        self.numeros_linea.insert('1.0', numeros)
        self.numeros_linea.config(state='disabled')
        
        self.numeros_linea.yview_moveto(posicion_scroll[0])
    
    def analizar_en_tiempo_real(self):
        """Analiza el código en tiempo real"""
        codigo = self.editor_texto.get('1.0', 'end-1c')
        
        # Análisis léxico
        self.tokens, errores_lexicos = self.analizador_lexico.analizar(codigo)
        
        # Análisis sintáctico
        errores_sintacticos = self.analizador_sintactico.analizar(self.tokens, codigo)
        
        # Combinar errores
        self.errores = errores_lexicos + errores_sintacticos
        
        self.actualizar_numeros_linea()
        self.mostrar_errores()
        self.mostrar_tokens()
        self.actualizar_estado()
    
    def mostrar_errores(self):
        """Muestra los errores en la interfaz"""
        self.texto_errores.config(state='normal')
        self.texto_errores.delete('1.0', 'end')
        
        if not self.errores:
            self.texto_errores.insert('1.0', "✅ No se encontraron errores\n\n", 'exito')
            self.texto_errores.tag_config('exito', foreground='#059669', font=('Arial', 12, 'bold'))
        else:
            errores_lexicos = [e for e in self.errores if e.tipo == 'lexico']
            errores_sintacticos = [e for e in self.errores if e.tipo == 'sintactico']
            
            if errores_lexicos:
                self.texto_errores.insert('end', "🔍 ERRORES LÉXICOS:\n\n", 'header_lex')
                for i, error in enumerate(errores_lexicos, 1):
                    self.texto_errores.insert('end', f"Error {i}:\n", 'titulo')
                    self.texto_errores.insert('end', f"📍 Línea {error.linea}, Columna {error.columna}\n", 'ubicacion')
                    self.texto_errores.insert('end', f"{error.mensaje}\n", 'mensaje')
                    self.texto_errores.insert('end', f"💡 {error.sugerencia}\n\n", 'sugerencia')
            
            if errores_sintacticos:
                self.texto_errores.insert('end', "⚙️ ERRORES SINTÁCTICOS:\n\n", 'header_sin')
                for i, error in enumerate(errores_sintacticos, 1):
                    self.texto_errores.insert('end', f"Error {i}:\n", 'titulo_sin')
                    self.texto_errores.insert('end', f"📍 Línea {error.linea}, Columna {error.columna}\n", 'ubicacion_sin')
                    self.texto_errores.insert('end', f"{error.mensaje}\n", 'mensaje_sin')
                    self.texto_errores.insert('end', f"💡 {error.sugerencia}\n\n", 'sugerencia_sin')
            
            # Configurar estilos
            self.texto_errores.tag_config('header_lex', foreground='#dc2626', font=('Arial', 12, 'bold'))
            self.texto_errores.tag_config('header_sin', foreground='#f59e0b', font=('Arial', 12, 'bold'))
            self.texto_errores.tag_config('titulo', foreground='#991b1b', font=('Arial', 10, 'bold'))
            self.texto_errores.tag_config('titulo_sin', foreground='#92400e', font=('Arial', 10, 'bold'))
            self.texto_errores.tag_config('ubicacion', foreground='#b91c1c')
            self.texto_errores.tag_config('ubicacion_sin', foreground='#b45309')
            self.texto_errores.tag_config('mensaje', foreground='#374151')
            self.texto_errores.tag_config('mensaje_sin', foreground='#374151')
            self.texto_errores.tag_config('sugerencia', foreground='#059669', font=('Arial', 9, 'italic'))
            self.texto_errores.tag_config('sugerencia_sin', foreground='#059669', font=('Arial', 9, 'italic'))
        
        self.texto_errores.config(state='disabled')
    
    def mostrar_tokens(self):
        """Muestra los tokens en la interfaz"""
        self.texto_tokens.config(state='normal')
        self.texto_tokens.delete('1.0', 'end')
        
        if not self.tokens:
            self.texto_tokens.insert('1.0', "No hay tokens para mostrar")
        else:
            self.texto_tokens.insert('1.0', f"📊 Total de tokens: {len(self.tokens)}\n\n", 'header')
            
            for i, token in enumerate(self.tokens, 1):
                linea_texto = f"{token.linea}:{token.columna}  "
                self.texto_tokens.insert('end', linea_texto, 'linea')
                self.texto_tokens.insert('end', f"[{token.tipo}]  ", f'tipo_{token.tipo}')
                self.texto_tokens.insert('end', f"{token.valor}\n", 'valor')
            
            # Configurar colores
            self.texto_tokens.tag_config('header', font=('Arial', 11, 'bold'))
            self.texto_tokens.tag_config('linea', foreground='#6b7280')
            self.texto_tokens.tag_config('tipo_PALABRA_RESERVADA', foreground='#7c3aed', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_IDENTIFICADOR', foreground='#2563eb', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_OPERADOR', foreground='#059669', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_DELIMITADOR', foreground='#ea580c', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_LITERAL_ENTERO', foreground='#dc2626', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_LITERAL_FLOTANTE', foreground='#dc2626', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_LITERAL_CADENA', foreground='#db2777', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('tipo_COMENTARIO', foreground='#6b7280', font=('Consolas', 9, 'italic'))
            self.texto_tokens.tag_config('tipo_ERROR_PALABRA', foreground='#dc2626', font=('Consolas', 9, 'bold'))
            self.texto_tokens.tag_config('valor', foreground='#374151')
        
        self.texto_tokens.config(state='disabled')
    
    def actualizar_estado(self):
        """Actualiza el indicador de estado"""
        errores_lexicos = len([e for e in self.errores if e.tipo == 'lexico'])
        errores_sintacticos = len([e for e in self.errores if e.tipo == 'sintactico'])
        
        if not self.errores:
            self.label_estado.config(text="✓ Sin errores", fg='#059669')
        elif errores_sintacticos > 0:
            self.label_estado.config(
                text=f"⚠ {errores_lexicos}L + {errores_sintacticos}S errores",
                fg='#f59e0b'
            )
        else:
            self.label_estado.config(text=f"⚠ {len(self.errores)} errores", fg='#dc2626')
    
    def cargar_archivo(self):
        """Carga un archivo de texto"""
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        
        if archivo:
            try:
                with open(archivo, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                
                self.editor_texto.delete('1.0', 'end')
                self.editor_texto.insert('1.0', contenido)
                self.nombre_archivo = archivo.split('/')[-1]
                self.analizar_en_tiempo_real()
                messagebox.showinfo("Éxito", f"Archivo '{self.nombre_archivo}' cargado")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{str(e)}")
    
    def guardar_codigo(self):
        """Guarda el código en un archivo"""
        archivo = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
            initialfile=self.nombre_archivo
        )
        
        if archivo:
            try:
                contenido = self.editor_texto.get('1.0', 'end-1c')
                with open(archivo, 'w', encoding='utf-8') as f:
                    f.write(contenido)
                messagebox.showinfo("Éxito", "Código guardado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{str(e)}")
    
    def descargar_log(self):
        """Genera y descarga el archivo LOG"""
        if not self.tokens:
            messagebox.showwarning("Advertencia", "No hay tokens para generar LOG")
            return
        
        archivo = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt")],
            initialfile=f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if archivo:
            try:
                log = self.generar_log()
                with open(archivo, 'w', encoding='utf-8') as f:
                    f.write(log)
                messagebox.showinfo("Éxito", "LOG generado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo generar LOG:\n{str(e)}")
    
    def generar_log(self):
        """Genera el contenido del archivo LOG"""
        log = "=" * 70 + "\n"
        log += "=== ANÁLISIS LÉXICO Y SINTÁCTICO - LOG ===\n"
        log += "=" * 70 + "\n"
        log += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        log += f"Archivo: {self.nombre_archivo}\n"
        log += f"Total de tokens: {len(self.tokens)}\n"
        log += f"Total de errores: {len(self.errores)}\n"
        log += "=" * 70 + "\n\n"
        
        # Tokens
        log += "TOKENS IDENTIFICADOS:\n"
        log += "-" * 70 + "\n"
        for i, token in enumerate(self.tokens, 1):
            log += f"\nToken {i}:\n"
            log += f"  Tipo: {token.tipo}\n"
            log += f"  Valor: {token.valor}\n"
            log += f"  Línea: {token.linea}, Columna: {token.columna}\n"
        
        # Errores
        if self.errores:
            log += "\n\n" + "=" * 70 + "\n"
            log += "ERRORES DETECTADOS:\n"
            log += "=" * 70 + "\n"
            
            errores_lexicos = [e for e in self.errores if e.tipo == 'lexico']
            errores_sintacticos = [e for e in self.errores if e.tipo == 'sintactico']
            
            if errores_lexicos:
                log += "\nERRORES LÉXICOS:\n"
                log += "-" * 70 + "\n"
                for i, error in enumerate(errores_lexicos, 1):
                    log += f"\nError {i}:\n"
                    log += f"  Línea: {error.linea}, Columna: {error.columna}\n"
                    log += f"  Mensaje: {error.mensaje}\n"
                    log += f"  Sugerencia: {error.sugerencia}\n"
            
            if errores_sintacticos:
                log += "\nERRORES SINTÁCTICOS:\n"
                log += "-" * 70 + "\n"
                for i, error in enumerate(errores_sintacticos, 1):
                    log += f"\nError {i}:\n"
                    log += f"  Línea: {error.linea}, Columna: {error.columna}\n"
                    log += f"  Mensaje: {error.mensaje}\n"
                    log += f"  Sugerencia: {error.sugerencia}\n"
        
        return log
    
    def limpiar_editor(self):
        """Limpia el editor"""
        respuesta = messagebox.askyesno("Confirmar", "¿Desea limpiar el editor?")
        if respuesta:
            self.editor_texto.delete('1.0', 'end')
            self.analizar_en_tiempo_real()
    
    def cargar_ejemplo_correcto(self):
        """Carga un ejemplo de código correcto"""
        ejemplo = """// Programa de ejemplo CORRECTO en español
entero edad = 25;
flotante altura = 1.75;
cadena nombre = "Juan Pérez";

/* Este es un comentario
   de múltiples líneas
   correctamente cerrado */

// Estructura condicional
si (edad >= 18) {
    imprimir("Mayor de edad");
} sino {
    imprimir("Menor de edad");
}

// Bucle mientras
entero contador = 0;
mientras (contador < 5) {
    imprimir("Contador:");
    contador = contador + 1;
}

// Variables de una letra (válidas)
entero x = 10;
entero y = 20;
entero i = 0;

// Operaciones válidas
si (x > 5 && y < 30) {
    entero resultado = x * y;
}
"""
        self.editor_texto.delete('1.0', 'end')
        self.editor_texto.insert('1.0', ejemplo)
        self.analizar_en_tiempo_real()
    
    def cargar_ejemplo_errores(self):
        """Carga un ejemplo con todos los tipos de errores"""
        ejemplo = """// Ejemplo con TODOS los errores posibles

// Error 1: Falta punto y coma
entero edad = 25

// Error 2: Operador inválido ========
si (edad >========== 18) {
    imprimir("Mayor de edad"
}

// Error 3: Operador <> inválido
mientras (contador <> 5) {
    imprimir("Contador:");
    contador = contador + 1;
}

// Error 4: Palabra reservada mal escrita
Si (edad > 18) {
    imprimir("Mayor");
}

// Error 5: Operador >> inválido
entero x = 5 >> 2;

// Error 6: Operador &&&& inválido
si (x > 5 &&&& y < 30) {
    entero z = 1;
}

// Error 7: Falta ; después de imprimir
si (edad >= 18) {
    imprimir("Mayor de edad")
} sino {
    imprimir("Menor de edad")
}

// Error 8: Comentario sin cerrar
/* Este comentario no está cerrado

// Error 9: Cadena sin cerrar
cadena mensaje = "Hola Mundo;

// Error 10: Paréntesis sin cerrar
mientras (contador < 5 {
    contador = contador + 1;
}

// Error 11: Dentro de bloques sin ;
entero contador = 0;
mientras (contador < 5) {
    imprimir("Contador:")
    contador = contador + 1;
}

// Error 12: Número con múltiples decimales
flotante pi = 3.14.15;

// Error 13: Operador & solo
si (x > 5 & y < 10) {
    entero z = 1;
}

// Error 14: Llave sin cerrar
si (edad > 30) {
    imprimir("Treintañero");
"""
        self.editor_texto.delete('1.0', 'end')
        self.editor_texto.insert('1.0', ejemplo)
        self.analizar_en_tiempo_real()

def main():
    root = tk.Tk()
    app = InterfazAnalizador(root)
    root.mainloop()

if __name__ == "__main__":
    main()