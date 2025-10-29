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
        # Palabras reservadas EXACTAS (case-sensitive)
        self.palabras_reservadas = {
            'si', 'sino', 'mientras', 'para', 'entero', 'flotante', 
            'cadena', 'retornar', 'funcion', 'verdadero', 'falso', 
            'imprimir', 'leer'
        }
        
        # Mapeo de errores comunes a sugerencias
        self.sugerencias_comunes = {
            'if': 'si', 'else': 'sino', 'while': 'mientras', 'for': 'para',
            'int': 'entero', 'float': 'flotante', 'string': 'cadena',
            'return': 'retornar', 'function': 'funcion', 'true': 'verdadero',
            'false': 'falso', 'print': 'imprimir', 'read': 'leer',
            'sipasa': 'si', 'sinos': 'sino', 'Si': 'si', 'Sino': 'sino'
        }
        
        self.operadores_dobles = ['==', '!=', '<=', '>=', '&&', '||']
        self.operadores_simples = ['+', '-', '*', '/', '%', '<', '>', '!', '=']
        self.delimitadores = ['(', ')', '{', '}', ';', ',']
    
    def sugerir_palabra_reservada(self, palabra):
        """Sugiere la palabra reservada correcta"""
        # Primero buscar en sugerencias exactas
        if palabra in self.sugerencias_comunes:
            return self.sugerencias_comunes[palabra]
        
        palabra_lower = palabra.lower()
        if palabra_lower in self.sugerencias_comunes:
            return self.sugerencias_comunes[palabra_lower]
        
        # No sugerir para identificadores muy cortos
        if len(palabra) <= 2:
            return None
        
        # Buscar palabras similares (solo para palabras de longitud similar)
        for reservada in self.palabras_reservadas:
            if self.es_similar(palabra_lower, reservada):
                return reservada
        
        return None
    
    def es_similar(self, palabra1, palabra2):
        """Verifica si dos palabras son similares"""
        # No sugerir si las palabras son muy diferentes en longitud
        if abs(len(palabra1) - len(palabra2)) > 2:
            return False
        
        # No sugerir para identificadores muy cortos (1-2 letras)
        if len(palabra1) <= 2 or len(palabra2) <= 2:
            return False
        
        # Calcular diferencias
        diferencias = 0
        max_len = max(len(palabra1), len(palabra2))
        
        for i in range(min(len(palabra1), len(palabra2))):
            if palabra1[i] != palabra2[i]:
                diferencias += 1
            if diferencias > 2:
                return False
        
        # Agregar diferencia por longitud
        diferencias += abs(len(palabra1) - len(palabra2))
        
        return diferencias <= 2
    
    def analizar(self, codigo):
        tokens = []
        errores = []
        lineas = codigo.split('\n')
        
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
                
                # Comentarios de bloque /* */
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
                    if identificador in self.palabras_reservadas:
                        tokens.append(Token('PALABRA_RESERVADA', identificador, num_linea, inicio_id + 1))
                    else:
                        # Verificar si es palabra reservada mal escrita
                        # Solo buscar sugerencias para palabras de 3+ caracteres
                        # o si está en el diccionario de errores comunes
                        sugerencia = None
                        
                        if identificador in self.sugerencias_comunes or identificador.lower() in self.sugerencias_comunes:
                            # Es un error común conocido
                            sugerencia = self.sugerir_palabra_reservada(identificador)
                        elif len(identificador) >= 3:
                            # Solo buscar similitudes para palabras de 3+ caracteres
                            sugerencia = self.sugerir_palabra_reservada(identificador)
                        
                        if sugerencia:
                            errores.append(Error(num_linea, inicio_id + 1,
                                               f"Palabra reservada mal escrita: '{identificador}'",
                                               f"¿Quisiste decir '{sugerencia}'?"))
                            tokens.append(Token('ERROR_PALABRA', identificador, num_linea, inicio_id + 1))
                        else:
                            # Es un identificador válido
                            tokens.append(Token('IDENTIFICADOR', identificador, num_linea, inicio_id + 1))
                    continue
                
                # Caracter no reconocido
                errores.append(Error(num_linea, pos + 1,
                                   f"Caracter no reconocido: '{linea[pos]}'",
                                   "Verificar si es un operador o símbolo válido"))
                pos += 1
        
        return tokens, errores

class AnalizadorSintactico:
    def __init__(self):
        pass
    
    def analizar(self, tokens, codigo):
        errores = []
        
        # Verificar delimitadores balanceados
        errores.extend(self.verificar_delimitadores(tokens))
        
        # Verificar estructuras de control
        errores.extend(self.verificar_estructuras(tokens))
        
        # Verificar declaraciones
        errores.extend(self.verificar_declaraciones(tokens))
        
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
                                           "Paréntesis ')' sin abrir",
                                           "Agregar '(' antes o eliminar ')'", 'sintactico'))
                    else:
                        pila_parentesis.pop()
                
                elif token.valor == '{':
                    pila_llaves.append(token)
                elif token.valor == '}':
                    if not pila_llaves:
                        errores.append(Error(token.linea, token.columna,
                                           "Llave '}' sin abrir",
                                           "Agregar '{' antes o eliminar '}'", 'sintactico'))
                    else:
                        pila_llaves.pop()
        
        for token in pila_parentesis:
            errores.append(Error(token.linea, token.columna,
                               "Paréntesis '(' sin cerrar",
                               "Agregar ')' al final", 'sintactico'))
        
        for token in pila_llaves:
            errores.append(Error(token.linea, token.columna,
                               "Llave '{' sin cerrar",
                               "Agregar '}' al final", 'sintactico'))
        
        return errores
    
    def verificar_estructuras(self, tokens):
        errores = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            if token.tipo == 'PALABRA_RESERVADA':
                # Estructuras que requieren paréntesis
                if token.valor in ['si', 'mientras', 'para']:
                    if i + 1 >= len(tokens) or tokens[i + 1].valor != '(':
                        errores.append(Error(token.linea, token.columna,
                                           f"Falta '(' después de '{token.valor}'",
                                           f"Usar: {token.valor} (condicion) {{ ... }}", 'sintactico'))
            i += 1
        
        return errores
    
    def verificar_declaraciones(self, tokens):
        errores = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            # Tipos de datos
            if token.tipo == 'PALABRA_RESERVADA' and token.valor in ['entero', 'flotante', 'cadena']:
                # Debe seguir un identificador
                if i + 1 >= len(tokens):
                    errores.append(Error(token.linea, token.columna,
                                       f"Declaración incompleta después de '{token.valor}'",
                                       f"Usar: {token.valor} nombre = valor;", 'sintactico'))
                elif tokens[i + 1].tipo not in ['IDENTIFICADOR', 'ERROR_PALABRA']:
                    errores.append(Error(token.linea, token.columna,
                                       f"Se esperaba identificador después de '{token.valor}'",
                                       f"Ejemplo: {token.valor} miVariable;", 'sintactico'))
                else:
                    # Buscar punto y coma
                    encontrado_puntocoma = False
                    for j in range(i + 2, min(i + 15, len(tokens))):
                        if tokens[j].valor == ';':
                            encontrado_puntocoma = True
                            break
                        if tokens[j].tipo == 'PALABRA_RESERVADA':
                            break
                    
                    if not encontrado_puntocoma and i + 1 < len(tokens):
                        errores.append(Error(tokens[i + 1].linea, tokens[i + 1].columna,
                                           f"Falta ';' al final de la declaración",
                                           "Agregar punto y coma al final", 'sintactico'))
            i += 1
        
        return errores

class InterfazAnalizador:
    def __init__(self, root):
        self.root = root
        self.root.title("Analizador Léxico y Sintáctico - Mini-Lenguaje")
        self.root.geometry("1400x900")
        
        # Configurar estilo
        style = ttk.Style()
        style.theme_use('clam')
        
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
        tk.Label(header, text="Lenguaje de Programacion Proyecto Automatas", 
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
        
        # Editor con números de línea
        editor_frame = tk.Frame(left_panel, bg='#1e293b')
        editor_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.numeros_linea = tk.Text(editor_frame, width=4, bg='#334155', fg='#94a3b8',
                                     font=('Consolas', 11), state='disabled', padx=5,
                                     takefocus=0, cursor='arrow')
        self.numeros_linea.pack(side='left', fill='y')
        
        # Crear scrollbar compartida
        scrollbar = tk.Scrollbar(editor_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.editor_texto = tk.Text(editor_frame, wrap='none',
                                   bg='#1e293b', fg='#10b981',
                                   font=('Consolas', 11), 
                                   insertbackground='white',
                                   yscrollcommand=scrollbar.set)
        self.editor_texto.pack(side='left', fill='both', expand=True)
        
        # Configurar scrollbar para controlar ambos widgets
        scrollbar.config(command=self.scroll_ambos)
        
        # Vincular eventos
        self.editor_texto.bind('<KeyRelease>', lambda e: self.analizar_en_tiempo_real())
        self.editor_texto.bind('<MouseWheel>', self.on_mousewheel)
        self.editor_texto.bind('<Button-4>', self.on_mousewheel)  # Linux scroll up
        self.editor_texto.bind('<Button-5>', self.on_mousewheel)  # Linux scroll down
        
        # Panel derecho - Análisis
        right_panel = tk.Frame(main_frame, bg='white', relief='solid', bd=1)
        right_panel.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        tk.Label(right_panel, text="📊 Análisis", 
                font=('Arial', 14, 'bold'), bg='white', pady=10).pack()
        
        # Notebook
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
                                              font=('Arial', 10), state='normal')
        texto_ref.pack(fill='both', expand=True, padx=10, pady=10)
        
        referencia = """📚 REFERENCIA DEL LENGUAJE

⚠️ REGLAS IMPORTANTES:
• Las palabras reservadas son SENSIBLES a mayúsculas
• Usa 'si' NO 'Si' o 'SI'
• Todas las declaraciones terminan con ';'
• Los bloques usan llaves { }
• Las condiciones usan paréntesis ( )

📝 PALABRAS RESERVADAS:
si, sino, mientras, para, entero, flotante, cadena,
retornar, funcion, verdadero, falso, imprimir, leer

🔧 OPERADORES:
Aritméticos: +  -  *  /  %
Relacionales: ==  !=  <  >  <=  >=
Lógicos: &&  ||  !
Asignación: =

💬 COMENTARIOS:
// Comentario de línea
/* Comentario de bloque */

✅ EJEMPLOS CORRECTOS:

entero edad = 25;
flotante altura = 1.75;
cadena nombre = "Juan";

si (edad >= 18) {
    imprimir("Mayor de edad");
} sino {
    imprimir("Menor de edad");
}

mientras (edad < 30) {
    edad = edad + 1;
}

❌ ERRORES COMUNES:

Si (x > 10)         // ❌ 'Si' debe ser 'si'
sipasa (x > 10)     // ❌ debe ser 'si'
entero x = 10       // ❌ falta ';'
si x > 10 {         // ❌ faltan paréntesis
si (x > 10          // ❌ falta ')'
{                   // ❌ llave sin cerrar
"""
        texto_ref.insert('1.0', referencia)
        texto_ref.config(state='disabled')
    
    def scroll_ambos(self, *args):
        """Desplaza ambos widgets de texto simultáneamente"""
        self.editor_texto.yview(*args)
        self.numeros_linea.yview(*args)
    
    def on_mousewheel(self, event):
        """Maneja el scroll con la rueda del mouse"""
        if event.num == 5 or event.delta < 0:
            # Scroll down
            self.editor_texto.yview_scroll(1, "units")
            self.numeros_linea.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            # Scroll up
            self.editor_texto.yview_scroll(-1, "units")
            self.numeros_linea.yview_scroll(-1, "units")
        return "break"
    
    def actualizar_numeros_linea(self):
        """Actualiza los números de línea"""
        texto = self.editor_texto.get('1.0', 'end-1c')
        num_lineas = texto.count('\n') + 1
        
        # Obtener posición actual del scroll antes de actualizar
        posicion_scroll = self.editor_texto.yview()
        
        self.numeros_linea.config(state='normal')
        self.numeros_linea.delete('1.0', 'end')
        numeros = '\n'.join(str(i) for i in range(1, num_lineas + 1))
        self.numeros_linea.insert('1.0', numeros)
        self.numeros_linea.config(state='disabled')
        
        # Restaurar posición del scroll
        self.numeros_linea.yview_moveto(posicion_scroll[0])
    
    def analizar_en_tiempo_real(self):
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
        respuesta = messagebox.askyesno("Confirmar", "¿Desea limpiar el editor?")
        if respuesta:
            self.editor_texto.delete('1.0', 'end')
            self.analizar_en_tiempo_real()
    
    def cargar_ejemplo_correcto(self):
        ejemplo = """// Programa de ejemplo CORRECTO en español
entero edad = 25;
flotante altura = 1.75;
cadena nombre = "Juan Pérez";

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

// Declaraciones múltiples
entero x = 10;
entero y = 20;
entero resultado = x + y;

// Operaciones
si (x > 5 && y < 30) {
    resultado = x * y;
}

// Bucle for
para (entero i = 0; i < 10; i = i + 1) {
    imprimir(i);
}
"""
        self.editor_texto.delete('1.0', 'end')
        self.editor_texto.insert('1.0', ejemplo)
        self.analizar_en_tiempo_real()
    
    def cargar_ejemplo_errores(self):
        ejemplo = """// Este código tiene VARIOS ERRORES para practicar

// Error 1: Falta punto y coma
entero edad = 25

// Error 2: Palabra reservada mal escrita (mayúscula)
Si (edad > 18) {
    imprimir("Mayor");
}

// Error 3: Palabra reservada inexistente
sipasa (edad < 60) {
    imprimir("Activo");
}

// Error 4: Cadena sin cerrar
cadena mensaje = "Hola Mundo;

// Error 5: Paréntesis sin cerrar
mientras (edad < 100 {
    edad = edad + 1;
}

// Error 6: Llave sin cerrar
si (edad > 30) {
    imprimir("Treintañero");

// Error 7: Falta paréntesis después de si
si edad >= 21 {
    imprimir("Puede votar");
}

// Error 8: Identificador inválido (empieza con número)
entero 2variable = 50;

// Error 9: Número con múltiples puntos
flotante pi = 3.14.15;

// Error 10: Palabra en inglés (debe ser en español)
if (edad > 10) {
    print("Error");
}
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