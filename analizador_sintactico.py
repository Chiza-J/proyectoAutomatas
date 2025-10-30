import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
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
    def __init__(self, linea, columna, mensaje, tipo='lexico'):
        self.linea = linea
        self.columna = columna
        self.mensaje = mensaje
        self.tipo = tipo
    
    def __repr__(self):
        return f"Error({self.tipo}, L{self.linea}:C{self.columna}, {self.mensaje})"

class AnalizadorLexico:
    def __init__(self):
        # ALFABETO: Palabras reservadas EXACTAS (solo estas son válidas)
        self.palabras_reservadas = {
            'si', 'sino', 'mientras', 'para', 'entero', 'flotante', 
            'cadena', 'retornar', 'funcion', 'verdadero', 'falso', 
            'imprimir', 'leer'
        }
        
        # ALFABETO: Operadores válidos
        self.operadores = {
            '==', '!=', '<=', '>=', '&&', '||',
            '+', '-', '*', '/', '%', '<', '>', '!', '='
        }
        
        # set de caracteres que pueden formar operadores
        self.operador_chars = set('=!<>+-*/%&|')

        # ALFABETO: Delimitadores
        self.delimitadores = {'(', ')', '{', '}', ';', ','}
        
        # Para validaciones de tipo léxicas inmediatas
        self.tipos_datos = {'entero', 'flotante', 'cadena'}
        # contexto_tipos se llenará tras tokenizar (declaraciones detectadas)
        self.contexto_tipos = {}  # nombre -> (tipo, linea)
        
    def _es_operador_valido(self, seq):
        """Verifica si la secuencia exacta seq es un operador permitido."""
        return seq in self.operadores
    
    def _inferir_tipo_literal_token(self, token):
        """Devuelve 'entero','flotante','cadena' o None para un token literal."""
        if token.tipo == 'LITERAL_ENTERO':
            return 'entero'
        if token.tipo == 'LITERAL_FLOTANTE':
            return 'flotante'
        if token.tipo == 'LITERAL_CADENA':
            return 'cadena'
        if token.tipo == 'PALABRA_RESERVADA' and token.valor in ('verdadero','falso'):
            return 'entero'
        return None

    def _validar_expresion_tipos(self, tokens_segmento, errores):
        """
        Inferir tipos de los operandos en la expresión y validar mezclas inválidas.
        - Retorna tipo resultante ('entero','flotante','cadena') o None si no se pudo inferir.
        - Añade errores a la lista 'errores' cuando detecta mezclas inválidas.
        """
        operand_types = []
        last_was_operator = True  # iniciar True para detectar operadores dobles al inicio
        i = 0
        while i < len(tokens_segmento):
            tk = tokens_segmento[i]
            if tk.tipo == 'DELIMITADOR' and tk.valor in ('(',')',','):
                last_was_operator = False
                i += 1
                continue

            if tk.tipo == 'OPERADOR':
                if last_was_operator and tk.valor != '!':  # '!' puede ser unario
                    errores.append(Error(tk.linea, tk.columna,
                                         f"secuencia inválida de operadores cerca de '{tk.valor}'", 'lexico'))
                last_was_operator = True
                i += 1
                continue

            if tk.tipo in ('LITERAL_ENTERO','LITERAL_FLOTANTE','LITERAL_CADENA'):
                tp = self._inferir_tipo_literal_token(tk)
                if tp:
                    operand_types.append((tp, tk))
                last_was_operator = False
                i += 1
                continue

            if tk.tipo == 'PALABRA_RESERVADA' and tk.valor in ('verdadero','falso'):
                operand_types.append(('entero', tk))
                last_was_operator = False
                i += 1
                continue

            if tk.tipo == 'IDENTIFICADOR':
                if tk.valor in self.contexto_tipos:
                    declared_type = self.contexto_tipos[tk.valor][0]
                    operand_types.append((declared_type, tk))
                else:
                    errores.append(Error(tk.linea, tk.columna,
                                         f"uso de identificador '{tk.valor}' sin declaración previa (para validar tipos)", 'lexico'))
                last_was_operator = False
                i += 1
                continue

            last_was_operator = False
            i += 1

        tipos_presentes = set([t for t, _ in operand_types])
        if not operand_types:
            return None

        # Cadena mezclada con numérico -> error
        if 'cadena' in tipos_presentes and len(tipos_presentes) > 1:
            for t, tk in operand_types:
                if t == 'cadena':
                    errores.append(Error(tk.linea, tk.columna, "mezcla de tipo 'cadena' con tipo numérico en la misma expresión", 'lexico'))
                    break
            return None

        if tipos_presentes == {'entero'}:
            return 'entero'
        if tipos_presentes <= {'entero','flotante'}:
            return 'flotante' if 'flotante' in tipos_presentes else 'entero'

        return None

    def analizar(self, codigo):
        tokens = []
        errores = []
        i = 0
        linea = 1
        columna = 1
        
        # reset contexto_tipos para cada análisis
        self.contexto_tipos = {}

        # --- TOKENIZACIÓN ---
        while i < len(codigo):
            char = codigo[i]
            
            # Espacios y saltos de línea
            if char == '\n':
                linea += 1
                columna = 1
                i += 1
                continue
            elif char == ' ' or char == '\t' or char == '\r':
                columna += 1
                i += 1
                continue
            
            # Comentarios de línea //
            if i + 1 < len(codigo) and codigo[i:i+2] == '//':
                col_inicio = columna
                comentario = '//'
                i += 2
                columna += 2
                while i < len(codigo) and codigo[i] != '\n':
                    comentario += codigo[i]
                    i += 1
                tokens.append(Token('COMENTARIO', comentario, linea, col_inicio))
                continue
            
            # Comentarios de bloque /* */
            if i + 1 < len(codigo) and codigo[i:i+2] == '/*':
                col_inicio = columna
                linea_inicio = linea
                comentario = '/*'
                i += 2
                columna += 2
                cerrado = False
                
                while i + 1 < len(codigo):
                    if codigo[i:i+2] == '*/':
                        comentario += '*/'
                        i += 2
                        columna += 2
                        cerrado = True
                        break
                    if codigo[i] == '\n':
                        linea += 1
                        columna = 1
                    else:
                        columna += 1
                    comentario += codigo[i]
                    i += 1
                
                if cerrado:
                    tokens.append(Token('COMENTARIO', comentario, linea_inicio, col_inicio))
                else:
                    errores.append(Error(linea_inicio, col_inicio, 
                                       "comentario de bloque sin cerrar", 'lexico'))
                continue
            
            # Cadenas de texto
            if char == '"' or char == "'":
                col_inicio = columna
                linea_inicio = linea
                comilla = char
                cadena = char
                i += 1
                columna += 1
                cerrada = False
                
                while i < len(codigo):
                    if codigo[i] == '\\':
                        cadena += codigo[i]
                        i += 1
                        columna += 1
                        if i < len(codigo):
                            cadena += codigo[i]
                            i += 1
                            columna += 1
                        continue
                    
                    if codigo[i] == comilla:
                        cadena += codigo[i]
                        i += 1
                        columna += 1
                        cerrada = True
                        break
                    
                    if codigo[i] == '\n':
                        break
                    
                    cadena += codigo[i]
                    i += 1
                    columna += 1
                
                if cerrada:
                    tokens.append(Token('LITERAL_CADENA', cadena, linea_inicio, col_inicio))
                else:
                    errores.append(Error(linea_inicio, col_inicio,
                                       f"cadena literal sin cerrar", 'lexico'))
                continue
            
            # Números
            if char.isdigit():
                col_inicio = columna
                numero = ''
                puntos = 0
                tiene_coma = False
                
                while i < len(codigo) and (codigo[i].isdigit() or codigo[i] in ['.',',']):
                    if codigo[i] == '.':
                        puntos += 1
                    elif codigo[i] == ',':
                        tiene_coma = True
                    numero += codigo[i]
                    i += 1
                    columna += 1
                #error si tiene coma
                if tiene_coma:
                    errores.append(Error(linea, col_inicio, f"numero mal formado '{numero}' (no se permiten comas dentro de un numero)", 'lexico'))
                    continue
                # error si tiene más de un punto decimal
                if puntos > 1:
                    errores.append(Error(linea, col_inicio, f"número mal formado '{numero}' (demasiados puntos decimales)", 'lexico'))
                    continue
                # Verificar si continúa con letras (ERROR)
                if i < len(codigo) and (codigo[i].isalpha() or codigo[i] == '_'):
                    invalido = numero  
                    while i < len(codigo) and (codigo[i].isalnum() or codigo[i] == '_'):
                        numero += codigo[i]
                        i += 1
                        columna += 1
                    errores.append(Error(linea, col_inicio,
                                       f"token invalido '{invalido}' - no pertenece al alfabeto", 'lexico'))
                    continue

                elif puntos == 1:
                    tokens.append(Token('LITERAL_FLOTANTE', numero, linea, col_inicio))
                else:
                    tokens.append(Token('LITERAL_ENTERO', numero, linea, col_inicio))
                continue
            
            # Operadores: capturar secuencia completa de caracteres operadores (ej: '>>==', '===', '+', '&&')
            if char in self.operador_chars:
                col_inicio = columna
                seq = ''
                j = i
                while j < len(codigo) and codigo[j] in self.operador_chars:
                    seq += codigo[j]
                    j += 1
                # Intentar descomponer seq en operadores válidos; solo aceptamos si resulta en EXACTAMENTE 1 operador válido
                k = 0
                operadores_encontrados = []
                fallo = False
                while k < len(seq):
                    matched = None
                    # probar 2-char match
                    if k+2 <= len(seq) and seq[k:k+2] in self.operadores:
                        matched = seq[k:k+2]
                        k += 2
                    elif seq[k] in {o for o in self.operadores if len(o) == 1}:
                        matched = seq[k]
                        k += 1
                    else:
                        fallo = True
                        break
                    operadores_encontrados.append(matched)

                if fallo or len(operadores_encontrados) != 1 or not self._es_operador_valido(operadores_encontrados[0]):
                    errores.append(Error(linea, col_inicio,
                                         f"secuencia de operadores inválida o no permitida '{seq}'", 'lexico'))
                    i = j
                    columna += len(seq)
                    continue
                else:
                    op = operadores_encontrados[0]
                    tokens.append(Token('OPERADOR', op, linea, col_inicio))
                    i = j
                    columna += len(op)
                    continue

            # Delimitadores
            if char in self.delimitadores:
                tokens.append(Token('DELIMITADOR', char, linea, columna))
                i += 1
                columna += 1
                continue
            
            # Identificadores y palabras reservadas
            if char.isalpha() or char == '_':
                col_inicio = columna
                palabra = ''
                
                while i < len(codigo) and (codigo[i].isalnum() or codigo[i] == '_'):
                    palabra += codigo[i]
                    i += 1
                    columna += 1
                
                if palabra in self.palabras_reservadas:
                    tokens.append(Token('PALABRA_RESERVADA', palabra, linea, col_inicio))
                else:
                    tokens.append(Token('IDENTIFICADOR', palabra, linea, col_inicio))
                continue
            
            # Carácter no reconocido
            errores.append(Error(linea, columna,
                               f"carácter '{char}' no pertenece al alfabeto", 'lexico'))
            i += 1
            columna += 1
        
        # --- FIN TOKENIZACIÓN ---

        # 1) PRIMERA PASADA: Construir contexto de tipos (declaraciones) y validar declaraciones con inicialización
        tlen = len(tokens)
        idx = 0
        while idx < tlen:
            tk = tokens[idx]
            if tk.tipo == 'PALABRA_RESERVADA' and tk.valor in self.tipos_datos:
                tipo_decl = tk.valor
                if idx + 1 < tlen and tokens[idx+1].tipo == 'IDENTIFICADOR':
                    nombre = tokens[idx+1].valor
                    if nombre in self.contexto_tipos:
                        errores.append(Error(tokens[idx+1].linea, tokens[idx+1].columna,
                                             f"variable '{nombre}' ya declarada en línea {self.contexto_tipos[nombre][1]}", 'lexico'))
                    else:
                        # Declaración OBLIGATORIA CON = según tus reglas
                        j = idx + 2
                        if j < tlen and tokens[j].tipo == 'OPERADOR' and tokens[j].valor == '=':
                            # recoger expresión hasta ';'
                            expr = []
                            k = j + 1
                            while k < tlen and tokens[k].valor != ';' and tokens[k].valor != '{' and tokens[k].valor != '}':
                                expr.append(tokens[k])
                                k += 1
                            inferred = self._validar_expresion_tipos(expr, errores)
                            # si inferimos tipo, comparar con tipo_decl
                            if inferred:
                                if tipo_decl == 'entero' and inferred == 'flotante':
                                    errores.append(Error(tk.linea, tk.columna,
                                                         f"declaración de tipo 'entero' con expresión 'flotante' -> mezcla de tipos no permitida", 'lexico'))
                                elif tipo_decl == 'cadena' and inferred in ('entero','flotante'):
                                    errores.append(Error(tk.linea, tk.columna,
                                                         f"declaración de tipo 'cadena' con expresión numérica -> mezcla de tipos no permitida", 'lexico'))
                            # registrar declaración (correcta o con error semántico)
                            self.contexto_tipos[nombre] = (tipo_decl, tokens[idx+1].linea)
                            idx = k
                            continue
                        else:
                            errores.append(Error(tokens[idx+1].linea, tokens[idx+1].columna,
                                               f"declaración de '{tipo_decl}' debe incluir asignación (ej: {tipo_decl} var = ...;)", 'lexico'))
                            # aún así registramos para evitar cascada de errores en validaciones posteriores
                            self.contexto_tipos[nombre] = (tipo_decl, tokens[idx+1].linea)
                            idx += 2
                            continue
                else:
                    errores.append(Error(tk.linea, tk.columna,
                                         f"se esperaba identificador después de '{tk.valor}'", 'lexico'))
            idx += 1

        # 2) Validaciones estructurales y de expresiones (ahora que contexto_tipos está poblado)
        for idx, token in enumerate(tokens):
            # 'mientras'
            if token.tipo == 'PALABRA_RESERVADA' and token.valor == 'mientras':
                if idx + 1 >= len(tokens) or tokens[idx + 1].valor != '(':
                    errores.append(Error(token.linea, token.columna,
                                       "estructura 'mientras' debe abrir con '(' después de 'mientras'", 'sintactico'))
                    continue

                condicion_tokens = []
                j = idx + 2
                parentesis_cerrado = False
                while j < len(tokens):
                    if tokens[j].valor == ')':
                        parentesis_cerrado = True
                        break
                    condicion_tokens.append(tokens[j])
                    j += 1

                if not parentesis_cerrado:
                    errores.append(Error(token.linea, token.columna,
                                 "estructura 'mientras' sin paréntesis de cierre ')'", 'sintactico'))
                    continue

                if len(condicion_tokens) == 0:
                    errores.append(Error(token.linea, token.columna,
                                 "condición vacía en 'mientras'", 'sintactico'))
                else:
                    cond_str = ''.join([t.valor for t in condicion_tokens])
                    if '==' not in cond_str and '<' not in cond_str and '>' not in cond_str and '<=' not in cond_str and '>=' not in cond_str and '!=' not in cond_str and '&&' not in cond_str and '||' not in cond_str:
                        errores.append(Error(token.linea, token.columna,
                                     f"condición inválida en 'mientras' → falta operador lógico o relacional", 'sintactico'))
                    if '====' in cond_str or '<<' in cond_str or '>>' in cond_str or '=<=' in cond_str:
                        errores.append(Error(token.linea, token.columna,
                                     f"operador repetido o mal formado en 'mientras' → '{cond_str}'", 'sintactico'))

                if j + 1 >= len(tokens) or tokens[j + 1].valor != '{':
                    errores.append(Error(token.linea, token.columna,
                                 "estructura 'mientras' debe abrir con llave '{' después de ')'", 'sintactico'))

            # 'si'
            if token.tipo == 'PALABRA_RESERVADA' and token.valor == 'si':
                if idx + 1 >= len(tokens) or tokens[idx + 1].valor != '(':
                    errores.append(Error(token.linea, token.columna,
                                       "se esperaba '(' después de 'si'", 'sintactico'))
                else:
                    condicion_tokens = []
                    j = idx + 2
                    nivel = 0
                    parentesis_cerrado = False
                    while j < len(tokens):
                        if tokens[j].valor == '(':
                            nivel += 1
                        elif tokens[j].valor == ')':
                            if nivel == 0:
                                parentesis_cerrado = True
                                break
                            else:
                                nivel -= 1
                        condicion_tokens.append(tokens[j])
                        j += 1

                    if not parentesis_cerrado:
                        errores.append(Error(token.linea, token.columna,
                                             "estructura 'si' sin paréntesis de cierre ')'", 'sintactico'))
                    else:
                        if len(condicion_tokens) == 0:
                            errores.append(Error(token.linea, token.columna,
                                                 "condición vacía en 'si'", 'sintactico'))
                        else:
                            cond_str = ''.join([t.valor for t in condicion_tokens])
                            if '==' not in cond_str and '<' not in cond_str and '>' not in cond_str and '<=' not in cond_str and '>=' not in cond_str and '!=' not in cond_str and '&&' not in cond_str and '||' not in cond_str:
                                errores.append(Error(token.linea, token.columna,
                                                     f"condición inválida en 'si' → falta operador lógico o relacional", 'sintactico'))
                            # Validar mezcla de tipos dentro de la condición
                            self._validar_expresion_tipos(condicion_tokens, errores)

                    if j + 1 >= len(tokens) or tokens[j + 1].valor != '{':
                        errores.append(Error(tokens[j].linea if j < len(tokens) else token.linea, 
                                             tokens[j].columna if j < len(tokens) else token.columna,
                                               f"se esperaba '{{' después de ')'", 'sintactico'))

            # 'sino'
            if token.tipo == 'PALABRA_RESERVADA' and token.valor == 'sino':
                if idx + 1 >= len(tokens) or tokens[idx + 1].valor != '{':
                    errores.append(Error(token.linea, token.columna,
                                         "estructura 'sino' no debe llevar paréntesis; debe seguir '{'", 'sintactico'))
                found_si_previo = False
                for k in range(0, idx):
                    if tokens[k].tipo == 'PALABRA_RESERVADA' and tokens[k].valor == 'si':
                        found_si_previo = True
                        break
                if not found_si_previo:
                    errores.append(Error(token.linea, token.columna,
                                         "'sino' debe ir después de un 'si' previamente declarado", 'sintactico'))

            # 'para'
            if token.tipo == 'PALABRA_RESERVADA' and token.valor == 'para':
                if idx + 1 >= len(tokens) or tokens[idx + 1].valor != '(':
                    errores.append(Error(token.linea, token.columna,
                                       "se esperaba '(' después de 'para'", 'sintactico'))
                else:
                    j = idx + 2
                    nivel = 0
                    pos_cierre = -1
                    while j < len(tokens):
                        if tokens[j].valor == '(':
                            nivel += 1
                        elif tokens[j].valor == ')':
                            if nivel == 0:
                                pos_cierre = j
                                break
                            else:
                                nivel -= 1
                        j += 1
                    if pos_cierre == -1:
                        errores.append(Error(token.linea, token.columna,
                                             "estructura 'para' sin paréntesis de cierre ')'", 'sintactico'))
                    else:
                        count_puntos = sum(1 for t in tokens[idx+2:pos_cierre] if t.valor == ';')
                        if count_puntos != 2:
                            errores.append(Error(tokens[idx+2].linea if idx+2 < len(tokens) else token.linea,
                                                 tokens[idx+2].columna if idx+2 < len(tokens) else token.columna,
                                                 "estructura 'para' debe tener dos ';' en la cabecera", 'sintactico'))
                        if pos_cierre + 1 >= len(tokens) or tokens[pos_cierre + 1].valor != '{':
                            errores.append(Error(tokens[pos_cierre].linea, tokens[pos_cierre].columna,
                                                 "se esperaba '{' después de ')' en 'para'", 'sintactico'))

        # 3) Revisar asignaciones posteriores y validar mezclas en expresiones complejas (B)
        i = 0
        while i < len(tokens):
            tk = tokens[i]
            if tk.tipo == 'IDENTIFICADOR' and i+1 < len(tokens) and tokens[i+1].tipo == 'OPERADOR' and tokens[i+1].valor == '=':
                var_name = tk.valor
                if var_name not in self.contexto_tipos:
                    errores.append(Error(tk.linea, tk.columna,
                                         f"variable '{var_name}' no declarada antes de la asignación", 'lexico'))
                j = i + 2
                expr_tokens = []
                while j < len(tokens) and tokens[j].valor != ';' and tokens[j].valor != '{' and tokens[j].valor != '}':
                    expr_tokens.append(tokens[j])
                    j += 1
                inferred = self._validar_expresion_tipos(expr_tokens, errores)
                if inferred and var_name in self.contexto_tipos:
                    declared_type = self.contexto_tipos[var_name][0]
                    if declared_type == 'entero' and inferred == 'flotante':
                        errores.append(Error(tk.linea, tk.columna,
                                             f"asignación inválida: variable 'entero' recibe expresión 'flotante'", 'lexico'))
                    if declared_type == 'cadena' and inferred in ('entero','flotante'):
                        errores.append(Error(tk.linea, tk.columna,
                                             f"asignación inválida: variable 'cadena' recibe expresión numérica", 'lexico'))
                i = j
                continue
            i += 1

        # 4) Validar secuencias inválidas de operadores entre tokens
        for idx in range(len(tokens)-1):
            t1 = tokens[idx]
            t2 = tokens[idx+1]
            if t1.tipo == 'OPERADOR' and t2.tipo == 'OPERADOR':
                if not (t1.valor == '!' and (t2.valor == '(' or t2.tipo in ('IDENTIFICADOR','LITERAL_ENTERO','LITERAL_FLOTANTE','LITERAL_CADENA'))):
                    errores.append(Error(t2.linea, t2.columna,
                                         f"secuencia inválida de operadores '{t1.valor}{t2.valor}'", 'lexico'))

        return tokens, errores
    


class AnalizadorSintactico:
    def __init__(self):
        self.palabras_reservadas = {
            'si', 'sino', 'mientras', 'para', 'entero', 'flotante', 
            'cadena', 'retornar', 'funcion', 'verdadero', 'falso', 
            'imprimir', 'leer'
        }
        self.estructuras_control = {'si', 'mientras', 'para'}
        self.tipos_datos = {'entero', 'flotante', 'cadena'}
        self.variables_declaradas = {}  # {nombre: (tipo, linea_declaracion)}
        self.funciones_declaradas = {}
        self.alcance_actual = []  # Stack de alcances
    
    def analizar(self, tokens):
        errores = []
        tokens_sin_comentarios = [t for t in tokens if t.tipo != 'COMENTARIO']
        
        # Reiniciar estado
        self.variables_declaradas = {}
        self.funciones_declaradas = {}
        self.alcance_actual = []
        
        # 1. Verificar delimitadores balanceados
        errores.extend(self.verificar_delimitadores(tokens_sin_comentarios))
        
        # 2. Primera pasada: recolectar declaraciones
        errores.extend(self.recolectar_declaraciones(tokens_sin_comentarios))
        
        # 3. Segunda pasada: verificar uso de variables
        errores.extend(self.verificar_uso_variables(tokens_sin_comentarios))
        
        # 4. Verificar estructuras de control
        errores.extend(self.verificar_estructuras(tokens_sin_comentarios))
        
        # 5. Verificar punto y coma
        errores.extend(self.verificar_puntos_coma(tokens_sin_comentarios))
        
        return errores
    
    def recolectar_declaraciones(self, tokens):
        """Primera pasada: recolectar todas las declaraciones de variables"""
        errores = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            # Declaración de variable: tipo identificador
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in self.tipos_datos:
                if i + 1 < len(tokens) and tokens[i + 1].tipo == 'IDENTIFICADOR':
                    var_nombre = tokens[i + 1].valor
                    var_tipo = token.valor
                    
                    # Verificar si ya fue declarada
                    if var_nombre in self.variables_declaradas:
                        errores.append(Error(tokens[i + 1].linea, tokens[i + 1].columna,
                                           f"variable '{var_nombre}' ya declarada en línea {self.variables_declaradas[var_nombre][1]}", 
                                           'semantico'))
                    else:
                        self.variables_declaradas[var_nombre] = (var_tipo, tokens[i + 1].linea)
                    
                    # Verificar punto y coma o asignación
                    if i + 2 < len(tokens):
                        if tokens[i + 2].valor == ';':
                            i += 3
                            continue
                        elif tokens[i + 2].valor == '=':
                            # Declaración con inicialización
                            i += 3
                            continue
                    
                    errores.append(Error(tokens[i + 1].linea, tokens[i + 1].columna,
                                       "declaración incompleta o sin ';'", 'sintactico'))
                    i += 2
                    continue
                else:
                    errores.append(Error(token.linea, token.columna,
                                       f"se esperaba identificador después de '{token.valor}'", 'sintactico'))
            
            # Declaración de función
            elif token.tipo == 'PALABRA_RESERVADA' and token.valor == 'funcion':
                if i + 1 < len(tokens) and tokens[i + 1].tipo == 'IDENTIFICADOR':
                    func_nombre = tokens[i + 1].valor
                    if func_nombre in self.funciones_declaradas:
                        errores.append(Error(tokens[i + 1].linea, tokens[i + 1].columna,
                                           f"función '{func_nombre}' ya declarada", 'semantico'))
                    else:
                        self.funciones_declaradas[func_nombre] = tokens[i + 1].linea
            
            i += 1
        
        return errores
    
    def verificar_uso_variables(self, tokens):
        """Verificar que las variables se usen después de declararse"""
        errores = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            # Si encontramos un identificador
            if token.tipo == 'IDENTIFICADOR':
                # Verificar contexto para determinar si es uso o declaración
                es_declaracion = False
                
                # Caso 1: Es una declaración (tipo identificador)
                if i > 0 and tokens[i - 1].tipo == 'PALABRA_RESERVADA' and tokens[i - 1].valor in self.tipos_datos:
                    es_declaracion = True
                
                # Caso 2: Es una declaración de función
                if i > 0 and tokens[i - 1].tipo == 'PALABRA_RESERVADA' and tokens[i - 1].valor == 'funcion':
                    es_declaracion = True
                
                # Si NO es declaración, verificar que exista
                if not es_declaracion:
                    if token.valor not in self.variables_declaradas and token.valor not in self.funciones_declaradas:
                        errores.append(Error(token.linea, token.columna,
                                           f"variable o función '{token.valor}' no declarada", 'semantico'))
            
            i += 1
        
        return errores
    
    def verificar_delimitadores(self, tokens):
        errores = []
        pila_parentesis = []
        pila_llaves = []
        
        for token in tokens:
            if token.tipo == 'DELIMITADOR':
                if token.valor == '(':
                    pila_parentesis.append(token)
                elif token.valor == ')':
                    if not pila_parentesis:
                        errores.append(Error(token.linea, token.columna,
                                           "')' sin '(' correspondiente", 'sintactico'))
                    else:
                        pila_parentesis.pop()
                elif token.valor == '{':
                    pila_llaves.append(token)
                elif token.valor == '}':
                    if not pila_llaves:
                        errores.append(Error(token.linea, token.columna,
                                           "'}' sin '{' correspondiente", 'sintactico'))
                    else:
                        pila_llaves.pop()
        
        for token in pila_parentesis:
            errores.append(Error(token.linea, token.columna,
                               "'(' sin cerrar", 'sintactico'))
        
        for token in pila_llaves:
            errores.append(Error(token.linea, token.columna,
                               "'{' sin cerrar", 'sintactico'))
        
        return errores
    
    def verificar_estructuras(self, tokens):
        errores = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in self.estructuras_control:
                # Debe seguir '('
                if i + 1 >= len(tokens) or tokens[i + 1].valor != '(':
                    errores.append(Error(token.linea, token.columna,
                                       f"se esperaba '(' después de '{token.valor}'", 'sintactico'))
                else:
                    # Buscar ')' y verificar '{'
                    nivel = 0
                    j = i + 1
                    pos_cierre = -1
                    
                    while j < len(tokens):
                        if tokens[j].valor == '(':
                            nivel += 1
                        elif tokens[j].valor == ')':
                            nivel -= 1
                            if nivel == 0:
                                pos_cierre = j
                                break
                        j += 1
                    
                    if pos_cierre != -1 and pos_cierre + 1 < len(tokens):
                        if tokens[pos_cierre + 1].valor != '{':
                            errores.append(Error(tokens[pos_cierre].linea, 
                                               tokens[pos_cierre].columna,
                                               f"se esperaba '{{' después de ')'", 'sintactico'))
            i += 1
        
        return errores
    
    def verificar_puntos_coma(self, tokens):
        errores = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            # Declaraciones de variables
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in self.tipos_datos:
                if i + 1 < len(tokens) and tokens[i + 1].tipo == 'IDENTIFICADOR':
                    # Buscar ; después de la declaración
                    j = i + 2
                    encontrado_puntocoma = False
                    
                    while j < len(tokens) and j < i + 20:
                        if tokens[j].valor == ';':
                            encontrado_puntocoma = True
                            break
                        if tokens[j].valor == '{' or tokens[j].tipo == 'PALABRA_RESERVADA':
                            break
                        j += 1
                    
                    if not encontrado_puntocoma:
                        errores.append(Error(tokens[i + 1].linea, tokens[i + 1].columna,
                                           "falta ';' al final de la declaración", 'sintactico'))
            
            # Asignaciones
            if token.tipo == 'IDENTIFICADOR' and i + 1 < len(tokens):
                if tokens[i + 1].tipo == 'OPERADOR' and tokens[i + 1].valor == '=':
                    # Verificar si está en un for
                    es_for = False
                    for k in range(max(0, i - 15), i):
                        if tokens[k].tipo == 'PALABRA_RESERVADA' and tokens[k].valor == 'para':
                            es_for = True
                            break
                    
                    if not es_for:
                        j = i + 2
                        encontrado_puntocoma = False
                        
                        while j < len(tokens) and j < i + 20:
                            if tokens[j].valor == ';':
                                encontrado_puntocoma = True
                                break
                            if tokens[j].valor == '{':
                                break
                            if tokens[j].tipo == 'PALABRA_RESERVADA':
                                break
                            j += 1
                        
                        if not encontrado_puntocoma:
                            errores.append(Error(token.linea, token.columna,
                                               "falta ';' después de la asignación", 'sintactico'))
            
            # Llamadas a funciones (imprimir, leer)
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in ['imprimir', 'leer']:
                nivel = 0
                j = i
                encontrado_puntocoma = False
                
                while j < len(tokens) and j < i + 30:
                    if tokens[j].valor == '(':
                        nivel += 1
                    elif tokens[j].valor == ')':
                        nivel -= 1
                        if nivel == 0 and j + 1 < len(tokens):
                            if tokens[j + 1].valor == ';':
                                encontrado_puntocoma = True
                            break
                    j += 1
                
                if nivel == 0 and not encontrado_puntocoma:
                    errores.append(Error(token.linea, token.columna,
                                       f"falta ';' después de '{token.valor}()'", 'sintactico'))
            
            i += 1
        
        return errores


# Interfaz gráfica
class AnalizadorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Analizador Léxico y Sintáctico")
        self.root.geometry("1400x800")
        
        # Variables
        self.tokens = []
        self.errores_lexicos = []
        self.errores_sintacticos = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2563eb", height=100)
        header.pack(fill=tk.X)
        
        title_label = tk.Label(header, text=" Analizador Léxico y Sintáctico",
                              font=("Arial", 24, "bold"), bg="#2563eb", fg="white")
        title_label.pack(pady=10)
        
        subtitle = tk.Label(header, text="Lenguaje de Programación Proyecto Autómatas",
                           font=("Arial", 12), bg="#2563eb", fg="white")
        subtitle.pack()
        
        # Toolbar
        toolbar = tk.Frame(self.root, bg="#f3f4f6", height=50)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(toolbar, text="Cargar Archivo", command=self.cargar_archivo,
                 bg="#6b7280", fg="white", font=("Arial", 10), padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="Ejemplo Correcto", command=self.ejemplo_correcto,
                 bg="#10b981", fg="white", font=("Arial", 10), padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="Ejemplo con Errores", command=self.ejemplo_errores,
                 bg="#f59e0b", fg="white", font=("Arial", 10), padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="Guardar", command=self.guardar_archivo,
                 bg="#3b82f6", fg="white", font=("Arial", 10), padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="LOG", command=self.mostrar_log,
                 bg="#8b5cf6", fg="white", font=("Arial", 10), padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        
        tk.Button(toolbar, text="Limpiar", command=self.limpiar,
                 bg="#ef4444", fg="white", font=("Arial", 10), padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        
        self.status_label = tk.Label(toolbar, text="⚠️ 0L + 0S errores", 
                                     font=("Arial", 11, "bold"), fg="#f59e0b")
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # Panel principal
        main_panel = tk.Frame(self.root)
        main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Editor de código
        editor_frame = tk.LabelFrame(main_panel, text="Editor de Código", 
                                    font=("Arial", 12, "bold"))
        editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.editor = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD,
                                               font=("Consolas", 11),
                                               bg="#1e293b", fg="#10b981",
                                               insertbackground="white")
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.editor.bind('<KeyRelease>', lambda e: self.analizar_codigo())
        
        # Panel de análisis
        analisis_frame = tk.LabelFrame(main_panel, text="Análisis",
                                      font=("Arial", 12, "bold"))
        analisis_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        # Notebook para tabs
        notebook = ttk.Notebook(analisis_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab Errores
        errores_frame = tk.Frame(notebook)
        notebook.add(errores_frame, text="Errores")
        
        self.errores_text = scrolledtext.ScrolledText(errores_frame, wrap=tk.WORD,
                                                     font=("Arial", 10),
                                                     bg="#ffffff", fg="#000000")
        self.errores_text.pack(fill=tk.BOTH, expand=True)
        
        # Tab Tokens
        tokens_frame = tk.Frame(notebook)
        notebook.add(tokens_frame, text="Tokens")
        
        self.tokens_text = scrolledtext.ScrolledText(tokens_frame, wrap=tk.WORD,
                                                    font=("Consolas", 9),
                                                    bg="#ffffff", fg="#000000")
        self.tokens_text.pack(fill=tk.BOTH, expand=True)
        
        # Tab Referencia
        ref_frame = tk.Frame(notebook)
        notebook.add(ref_frame, text="Referencia")
        
        self.ref_text = scrolledtext.ScrolledText(ref_frame, wrap=tk.WORD,
                                                 font=("Consolas", 9),
                                                 bg="#eff6ff", fg="#1e40af")
        self.ref_text.pack(fill=tk.BOTH, expand=True)
        self.mostrar_referencia()
        
        # Label de conteo
        self.token_count_label = tk.Label(analisis_frame, text="Total de tokens: 0",
                                         font=("Arial", 10, "bold"))
        self.token_count_label.pack(pady=5)
    
    def mostrar_referencia(self):
        referencia = """

          ALFABETO DEL LENGUAJE FORMAL                

 PALABRAS RESERVADAS (solo estas son válidas):
   • si, sino, mientras, para
   • entero, flotante, cadena
   • retornar, funcion
   • verdadero, falso
   • imprimir, leer

 OPERADORES:
   • Aritméticos: +, -, *, /, %
   • Relacionales: ==, !=, <, >, <=, >=
   • Lógicos: &&, ||, !
   • Asignación: =

 DELIMITADORES:
   • Paréntesis: ( )
   • Llaves: { }
   • Punto y coma: ;
   • Coma: ,

 IDENTIFICADORES:
   • Inician con letra o guión bajo
   • Pueden contener letras, números y guión bajo
   • Ejemplos: x, contador, _temp, var123

 LITERALES:
   • Enteros: 25, 100, 0
   • Flotantes: 1.75, 3.14, 0.5
   • Cadenas: "texto", 'texto'

 COMENTARIOS:
   • Línea: // comentario
   • Bloque: /* comentario */


 REGLAS SEMÁNTICAS:
   1. Las variables DEBEN declararse antes de usarse
   2. No se pueden redeclarar variables
   3. Las palabras deben estar en el alfabeto
   4. Los bloques deben estar correctamente delimitados
"""
        self.ref_text.insert(1.0, referencia)
        self.ref_text.config(state=tk.DISABLED)
    
    def analizar_codigo(self):
        codigo = self.editor.get(1.0, tk.END)
        
        # Análisis léxico
        analizador_lexico = AnalizadorLexico()
        self.tokens, self.errores_lexicos = analizador_lexico.analizar(codigo)
        
        # Análisis sintáctico y semántico
        analizador_sintactico = AnalizadorSintactico()
        self.errores_sintacticos = analizador_sintactico.analizar(self.tokens)
        
        # Actualizar interfaz
        self.actualizar_tokens()
        self.actualizar_errores()
        self.actualizar_status()
    
    def actualizar_tokens(self):
        self.tokens_text.delete(1.0, tk.END)
        
        # Configurar tags para colores según tipo de token
        self.tokens_text.tag_config("comentario", foreground="#059669", font=("Consolas", 9, "italic"))
        self.tokens_text.tag_config("palabra_reservada", foreground="#7c3aed", font=("Consolas", 9, "bold"))
        self.tokens_text.tag_config("identificador", foreground="#0891b2", font=("Consolas", 9))
        self.tokens_text.tag_config("literal_entero", foreground="#dc2626", font=("Consolas", 9))
        self.tokens_text.tag_config("literal_flotante", foreground="#c026d3", font=("Consolas", 9))
        self.tokens_text.tag_config("literal_cadena", foreground="#ea580c", font=("Consolas", 9))
        self.tokens_text.tag_config("operador", foreground="#059669", font=("Consolas", 9, "bold"))
        self.tokens_text.tag_config("delimitador", foreground="#ea580c", font=("Consolas", 9, "bold"))
        self.tokens_text.tag_config("numero", foreground="#6b7280", font=("Consolas", 9))
        
        for i, token in enumerate(self.tokens, 1):
            # Número de línea
            self.tokens_text.insert(tk.END, f"{i}:{token.linea}  ", "numero")
            
            # Tipo de token entre corchetes con color
            tipo_tag = token.tipo.lower()
            self.tokens_text.insert(tk.END, f"[{token.tipo}]", tipo_tag)
            
            # Espaciado
            espacios = " " * (25 - len(token.tipo))
            self.tokens_text.insert(tk.END, espacios)
            
            # Valor del token
            self.tokens_text.insert(tk.END, f"{token.valor}\n", tipo_tag)
        
        self.token_count_label.config(text=f"Total de tokens: {len(self.tokens)}")
    
    def actualizar_errores(self):
        self.errores_text.delete(1.0, tk.END)
        
        # Configurar tags para colores
        self.errores_text.tag_config("titulo_lexico", foreground="#dc2626", font=("Arial", 11, "bold"))
        self.errores_text.tag_config("titulo_sintactico", foreground="#ea580c", font=("Arial", 11, "bold"))
        self.errores_text.tag_config("error_num", foreground="#000000", font=("Arial", 10, "bold"))
        self.errores_text.tag_config("ubicacion", foreground="#dc2626", font=("Arial", 10, "bold"))
        self.errores_text.tag_config("mensaje", foreground="#000000", font=("Arial", 10))
        
        if not self.errores_lexicos and not self.errores_sintacticos:
            self.errores_text.insert(tk.END, "✅ ¡Código correcto! No se encontraron errores.\n\n")
            self.errores_text.insert(tk.END, "El código cumple con:\n")
            self.errores_text.insert(tk.END, "  • Todas las palabras pertenecen al alfabeto\n")
            self.errores_text.insert(tk.END, "  • Variables declaradas antes de usarse\n")
            self.errores_text.insert(tk.END, "  • Sintaxis correcta\n")
            self.errores_text.insert(tk.END, "  • Delimitadores balanceados\n")
            return
        
        # ERRORES LÉXICOS
        if self.errores_lexicos:
            self.errores_text.insert(tk.END, "🔴 ERRORES LÉXICOS:\n\n", "titulo_lexico")
            
            for i, error in enumerate(self.errores_lexicos, 1):
                # Error N:
                self.errores_text.insert(tk.END, f"Error {i}:\n", "error_num")
                # 📍 Línea X, Columna Y
                self.errores_text.insert(tk.END, f"📍 Línea {error.linea}, Columna {error.columna}\n", "ubicacion")
                # Mensaje del error
                self.errores_text.insert(tk.END, f"{error.mensaje}\n\n", "mensaje")
        
        # ERRORES SINTÁCTICOS
        if self.errores_sintacticos:
            self.errores_text.insert(tk.END, "⚠️ ERRORES SINTÁCTICOS:\n\n", "titulo_sintactico")
            
            for i, error in enumerate(self.errores_sintacticos, 1):
                # Error N:
                self.errores_text.insert(tk.END, f"Error {i}:\n", "error_num")
                # 📍 Línea X, Columna Y
                self.errores_text.insert(tk.END, f"📍 Línea {error.linea}, Columna {error.columna}\n", "ubicacion")
                # Mensaje del error
                self.errores_text.insert(tk.END, f"{error.mensaje}\n\n", "mensaje")
    
    def actualizar_status(self):
        num_lexicos = len(self.errores_lexicos)
        num_sintacticos = len(self.errores_sintacticos)
        total = num_lexicos + num_sintacticos
        
        if total == 0:
            self.status_label.config(text="✅ 0L + 0S errores", fg="#10b981")
        else:
            self.status_label.config(text=f"⚠️ {num_lexicos}L + {num_sintacticos}S errores", fg="#ef4444")
    
    def cargar_archivo(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                    self.editor.delete(1.0, tk.END)
                    self.editor.insert(1.0, contenido)
                    self.analizar_codigo()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{str(e)}")
    
    def guardar_archivo(self):
        filename = filedialog.asksaveasfilename(
            title="Guardar archivo",
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    contenido = self.editor.get(1.0, tk.END)
                    f.write(contenido)
                messagebox.showinfo("Éxito", "Archivo guardado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{str(e)}")
    
    def ejemplo_correcto(self):
        codigo = """// Programa de ejemplo CORRECTO en español
entero edad = 25;
flotante altura = 1.75;
cadena nombre = "Juan Pérez";

/* Este es un comentario
   de bloque multilínea
   correcto */

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
"""
        self.editor.delete(1.0, tk.END)
        self.editor.insert(1.0, codigo)
        self.analizar_codigo()
    
    def ejemplo_errores(self):
        codigo = """// Ejemplo con MÚLTIPLES ERRORES

// ERROR: variable no declarada antes de usar
resultado = x + 10;

// ERROR: palabra 'enteros' no está en el alfabeto (debería ser 'entero')
enteros numero = 5;

// ERROR: variable 'y' no declarada
entero z = y * 2;

// ERROR: falta punto y coma
entero valor = 100

// ERROR: 'if' no está en el alfabeto (debería ser 'si')
if (valor > 50) {
    imprimir("Grande");
}

// ERROR: paréntesis sin cerrar
si (numero < 10 {
    imprimir("Pequeño");
}

// ERROR: número mal formado
entero malNumero = 12.34.56;

// ERROR: identificador inválido (empieza con número)
3variable = 10;

// ERROR: carácter no reconocido
entero test @ 5;
"""
        self.editor.delete(1.0, tk.END)
        self.editor.insert(1.0, codigo)
        self.analizar_codigo()
    
    def limpiar(self):
        self.editor.delete(1.0, tk.END)
        self.tokens_text.delete(1.0, tk.END)
        self.errores_text.delete(1.0, tk.END)
        self.tokens = []
        self.errores_lexicos = []
        self.errores_sintacticos = []
        self.actualizar_status()
    
    def mostrar_log(self):
        log_window = tk.Toplevel(self.root)
        log_window.title("LOG de Análisis")
        log_window.geometry("800x600")
        
        log_text = scrolledtext.ScrolledText(log_window, wrap=tk.WORD,
                                            font=("Consolas", 10))
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = f"""

              LOG DE ANÁLISIS - {timestamp}              



RESUMEN DEL ANÁLISIS

Total de tokens encontrados: {len(self.tokens)}
Errores léxicos: {len(self.errores_lexicos)}
Errores sintácticos/semánticos: {len(self.errores_sintacticos)}
Estado: {"✅ CORRECTO" if not (self.errores_lexicos or self.errores_sintacticos) else "❌ CON ERRORES"}


TOKENS IDENTIFICADOS

"""
        
        for i, token in enumerate(self.tokens, 1):
            log_content += f"{i:3d}. L{token.linea}:C{token.columna:2d} | {token.tipo:20s} | {token.valor}\n"
        
        if self.errores_lexicos or self.errores_sintacticos:
            log_content += """

ERRORES DETECTADOS

"""
            todos_errores = self.errores_lexicos + self.errores_sintacticos
            todos_errores.sort(key=lambda e: (e.linea, e.columna))
            
            for i, error in enumerate(todos_errores, 1):
                tipo = error.tipo.upper()
                log_content += f"{i:2d}. [{tipo:10s}] L{error.linea}:C{error.columna} - {error.mensaje}\n"
        
        log_content += """

VALIDACIONES REALIZADAS

✓ Verificación de alfabeto (solo palabras reservadas válidas)
✓ Análisis léxico (tokens, operadores, delimitadores)
✓ Análisis sintáctico (estructura del código)
✓ Análisis semántico (variables declaradas antes de uso)
✓ Balanceo de delimitadores (paréntesis, llaves)
✓ Verificación de punto y coma


"""
        
        log_text.insert(1.0, log_content)
        log_text.config(state=tk.DISABLED)
        
        # Botón para guardar log
        btn_frame = tk.Frame(log_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        def guardar_log():
            filename = filedialog.asksaveasfilename(
                title="Guardar LOG",
                defaultextension=".log",
                filetypes=[("Archivo LOG", "*.log"), ("Archivo de texto", "*.txt")]
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(log_content)
                    messagebox.showinfo("Éxito", "LOG guardado correctamente")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo guardar el LOG:\n{str(e)}")
        
        tk.Button(btn_frame, text="Guardar LOG", command=guardar_log,
                 bg="#3b82f6", fg="white", font=("Arial", 10), padx=15, pady=5).pack(side=tk.LEFT)
        
        tk.Button(btn_frame, text="Cerrar", command=log_window.destroy,
                 bg="#6b7280", fg="white", font=("Arial", 10), padx=15, pady=5).pack(side=tk.RIGHT)

# Ejecutar la aplicación
if __name__ == "__main__":
    root = tk.Tk()
    app = AnalizadorApp(root)
    root.mainloop()