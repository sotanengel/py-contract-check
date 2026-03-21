//! `rust-contract-checks` 向けの procedural macro 群です。
//!
//! 現在は `#[contract(...)]` を提供し、sync な関数とメソッドへ契約検証コードを展開します。
//!
#![forbid(unsafe_code)]

use proc_macro::TokenStream;

use proc_macro2::Span;
use quote::{format_ident, quote};
use syn::{
    parenthesized,
    parse::{Parse, ParseStream},
    parse_macro_input,
    punctuated::Punctuated,
    spanned::Spanned,
    Expr, FnArg, ImplItemFn, ItemFn, LitStr, Pat, Result, ReturnType, Token, Type,
};

/// 関数やメソッドに契約条項を付与します。
///
/// ```ignore
/// #[contract(
///     pre(x > 0, "入力は正値"),
///     post(*ret >= x, "戻り値は入力以上"),
///     error(matches!(err, MyError::BadInput), "許可された失敗のみ"),
///     invariant(self.balance >= 0, "残高は非負"),
///     pure("外部状態を読まない"),
///     panic_free("契約違反以外ではpanicしない")
/// )]
/// ```
#[proc_macro_attribute]
pub fn contract(attr: TokenStream, item: TokenStream) -> TokenStream {
    let arguments = parse_macro_input!(attr as ContractArguments);
    let item_tokens = proc_macro2::TokenStream::from(item.clone());

    if let Ok(function) = syn::parse2::<ItemFn>(item_tokens.clone()) {
        if function.sig.receiver().is_none() {
            return expand_free_function(arguments, function).into();
        }
    }

    if let Ok(method) = syn::parse2::<ImplItemFn>(item_tokens) {
        return expand_method(arguments, method).into();
    }

    syn::Error::new(
        Span::call_site(),
        "#[contract] は関数または実装メソッドにのみ適用できます",
    )
    .to_compile_error()
    .into()
}

struct ContractArguments {
    items: Vec<ContractItem>,
}

impl Parse for ContractArguments {
    fn parse(input: ParseStream<'_>) -> Result<Self> {
        let items = Punctuated::<ContractItem, Token![,]>::parse_terminated(input)?
            .into_iter()
            .collect();
        Ok(Self { items })
    }
}

enum ContractItem {
    Pre(ClauseSpec),
    Post(ClauseSpec),
    Error(ClauseSpec),
    Invariant(ClauseSpec),
    Pure(Option<LitStr>),
    PanicFree(Option<LitStr>),
}

struct ClauseSpec {
    expr: Expr,
    message: Option<LitStr>,
}

mod keywords {
    syn::custom_keyword!(pre);
    syn::custom_keyword!(post);
    syn::custom_keyword!(error);
    syn::custom_keyword!(invariant);
    syn::custom_keyword!(pure);
    syn::custom_keyword!(panic_free);
}

impl Parse for ContractItem {
    fn parse(input: ParseStream<'_>) -> Result<Self> {
        if input.peek(keywords::pre) {
            input.parse::<keywords::pre>()?;
            return Ok(Self::Pre(parse_clause_spec(input)?));
        }

        if input.peek(keywords::post) {
            input.parse::<keywords::post>()?;
            return Ok(Self::Post(parse_clause_spec(input)?));
        }

        if input.peek(keywords::error) {
            input.parse::<keywords::error>()?;
            return Ok(Self::Error(parse_clause_spec(input)?));
        }

        if input.peek(keywords::invariant) {
            input.parse::<keywords::invariant>()?;
            return Ok(Self::Invariant(parse_clause_spec(input)?));
        }

        if input.peek(keywords::pure) {
            input.parse::<keywords::pure>()?;
            return Ok(Self::Pure(parse_marker_message(input)?));
        }

        if input.peek(keywords::panic_free) {
            input.parse::<keywords::panic_free>()?;
            return Ok(Self::PanicFree(parse_marker_message(input)?));
        }

        Err(input.error("未知の契約指定です"))
    }
}

fn parse_clause_spec(input: ParseStream<'_>) -> Result<ClauseSpec> {
    let content;
    parenthesized!(content in input);
    let expr = content.parse::<Expr>()?;
    let message = if content.is_empty() {
        None
    } else {
        content.parse::<Token![,]>()?;
        Some(content.parse::<LitStr>()?)
    };

    if !content.is_empty() {
        return Err(content.error("契約指定の末尾に余分なトークンがあります"));
    }

    Ok(ClauseSpec { expr, message })
}

fn parse_marker_message(input: ParseStream<'_>) -> Result<Option<LitStr>> {
    if !input.peek(syn::token::Paren) {
        return Ok(None);
    }

    let content;
    parenthesized!(content in input);

    if content.is_empty() {
        return Ok(None);
    }

    let message = content.parse::<LitStr>()?;

    if !content.is_empty() {
        return Err(content.error("marker指定には文字列メッセージのみ渡せます"));
    }

    Ok(Some(message))
}

fn expand_free_function(
    arguments: ContractArguments,
    function: ItemFn,
) -> proc_macro2::TokenStream {
    match expand_function_like(FunctionLike::Free(function), arguments) {
        Ok(expanded) => expanded,
        Err(error) => error.to_compile_error(),
    }
}

fn expand_method(arguments: ContractArguments, method: ImplItemFn) -> proc_macro2::TokenStream {
    match expand_function_like(FunctionLike::Method(method), arguments) {
        Ok(expanded) => expanded,
        Err(error) => error.to_compile_error(),
    }
}

enum FunctionLike {
    Free(ItemFn),
    Method(ImplItemFn),
}

impl FunctionLike {
    fn sig(&self) -> &syn::Signature {
        match self {
            Self::Free(function) => &function.sig,
            Self::Method(method) => &method.sig,
        }
    }

    fn attrs(&self) -> &[syn::Attribute] {
        match self {
            Self::Free(function) => &function.attrs,
            Self::Method(method) => &method.attrs,
        }
    }

    fn vis(&self) -> Option<&syn::Visibility> {
        match self {
            Self::Free(function) => Some(&function.vis),
            Self::Method(_) => None,
        }
    }

    fn block(&self) -> &syn::Block {
        match self {
            Self::Free(function) => &function.block,
            Self::Method(method) => &method.block,
        }
    }
}

fn expand_function_like(
    function_like: FunctionLike,
    arguments: ContractArguments,
) -> Result<proc_macro2::TokenStream> {
    let signature = function_like.sig().clone();
    let function_name = &signature.ident;
    let contract_crate = quote!(::rust_contract_checks);

    if signature.asyncness.is_some() {
        return Err(syn::Error::new(
            signature.asyncness.span(),
            "現在の #[contract] は async fn を未サポートです",
        ));
    }

    if signature.constness.is_some() {
        return Err(syn::Error::new(
            signature.constness.span(),
            "現在の #[contract] は const fn を未サポートです",
        ));
    }

    let mut preconditions = Vec::new();
    let mut postconditions = Vec::new();
    let mut error_contracts = Vec::new();
    let mut invariants = Vec::new();
    let mut pure_marker = false;
    let mut purity_message = None;
    let mut panic_free_marker = false;
    let mut panic_contract_message = None;

    for item in arguments.items {
        match item {
            ContractItem::Pre(spec) => preconditions.push(spec),
            ContractItem::Post(spec) => postconditions.push(spec),
            ContractItem::Error(spec) => error_contracts.push(spec),
            ContractItem::Invariant(spec) => invariants.push(spec),
            ContractItem::Pure(message) => {
                pure_marker = true;
                purity_message = message;
            }
            ContractItem::PanicFree(message) => {
                panic_free_marker = true;
                panic_contract_message = message;
            }
        }
    }

    if pure_marker && has_mutable_input(&signature) {
        return Err(syn::Error::new(
            function_name.span(),
            "pure 契約つき関数は &mut self または &mut 引数を受け取れません",
        ));
    }

    let returns_result = returns_result_type(&signature.output);

    if !returns_result && !error_contracts.is_empty() {
        return Err(syn::Error::new(
            function_name.span(),
            "error 契約は Result を返す関数にのみ指定できます",
        ));
    }

    let function_path = quote! { concat!(module_path!(), "::", stringify!(#function_name)) };
    let pre_inputs = input_snapshots(&signature.inputs, &contract_crate);
    let post_inputs = input_snapshots(&signature.inputs, &contract_crate);
    let attrs = function_like.attrs().to_vec();
    let vis = function_like.vis().cloned();
    let block = function_like.block().clone();
    let metadata_entries = metadata_entries(
        &preconditions,
        &postconditions,
        &error_contracts,
        &invariants,
        pure_marker,
        purity_message.as_ref(),
        panic_free_marker,
        panic_contract_message.as_ref(),
        &contract_crate,
    );

    let pre_checks = clause_checks(
        &preconditions,
        "Precondition",
        &contract_crate,
        &function_path,
        &pre_inputs,
    );
    let pre_invariants = clause_checks(
        &invariants,
        "Invariant",
        &contract_crate,
        &function_path,
        &pre_inputs,
    );
    let post_invariants = clause_checks(
        &invariants,
        "Invariant",
        &contract_crate,
        &function_path,
        &post_inputs,
    );
    let post_checks = if returns_result {
        result_post_checks(
            &postconditions,
            &contract_crate,
            &function_path,
            &post_inputs,
        )
    } else {
        clause_checks_with_binding(
            &postconditions,
            "Postcondition",
            quote! { let ret = &__contract_result; },
            &contract_crate,
            &function_path,
            &post_inputs,
        )
    };
    let error_checks = result_error_checks(
        &error_contracts,
        &contract_crate,
        &function_path,
        &post_inputs,
    );

    let metadata_ident = format_ident!("__RUST_CONTRACT_CHECKS_METADATA_{}", function_name);
    let metadata_accessor = format_ident!("__rust_contract_checks_metadata_{}", function_name);
    let metadata_const = quote! {
        #[doc(hidden)]
        #[allow(non_upper_case_globals)]
        pub const #metadata_ident: #contract_crate::ContractMetadata = #contract_crate::ContractMetadata::new(
            #function_path,
            &[#(#metadata_entries),*]
        );

        #[doc(hidden)]
        pub fn #metadata_accessor() -> &'static #contract_crate::ContractMetadata {
            &#metadata_ident
        }
    };

    let expanded_body = quote! {
        if #contract_crate::contracts_enabled() {
            #(#pre_checks)*
            #(#pre_invariants)*
        }

        let __contract_result = (|| #block)();

        if #contract_crate::contracts_enabled() {
            #(#post_checks)*
            #error_checks
            #(#post_invariants)*
        }

        __contract_result
    };

    let output = match function_like {
        FunctionLike::Free(function) => {
            let sig = function.sig;
            let visibility = match vis {
                Some(visibility) => visibility,
                None => unreachable!("free function visibility must exist"),
            };
            quote! {
                #metadata_const
                #(#attrs)*
                #visibility #sig {
                    #expanded_body
                }
            }
        }
        FunctionLike::Method(method) => {
            let sig = method.sig;
            quote! {
                #(#attrs)*
                #sig {
                    #expanded_body
                }
            }
        }
    };

    Ok(output)
}

fn has_mutable_input(signature: &syn::Signature) -> bool {
    signature.inputs.iter().any(|argument| match argument {
        FnArg::Receiver(receiver) => receiver.mutability.is_some(),
        FnArg::Typed(typed) => matches!(
            typed.ty.as_ref(),
            Type::Reference(reference) if reference.mutability.is_some()
        ),
    })
}

fn returns_result_type(output: &ReturnType) -> bool {
    let ReturnType::Type(_, ty) = output else {
        return false;
    };

    let Type::Path(type_path) = ty.as_ref() else {
        return false;
    };

    match type_path.path.segments.last() {
        Some(segment) => segment.ident == "Result",
        None => false,
    }
}

fn input_snapshots(
    arguments: &syn::punctuated::Punctuated<FnArg, Token![,]>,
    contract_crate: &proc_macro2::TokenStream,
) -> Vec<proc_macro2::TokenStream> {
    arguments
        .iter()
        .filter_map(|argument| match argument {
            FnArg::Receiver(_) => Some(quote! {
                #contract_crate::input_snapshot("self", &self)
            }),
            FnArg::Typed(typed) => match typed.pat.as_ref() {
                Pat::Ident(identifier) => {
                    let name = LitStr::new(&identifier.ident.to_string(), identifier.ident.span());
                    let binding = &identifier.ident;
                    Some(quote! {
                        #contract_crate::input_snapshot(#name, &#binding)
                    })
                }
                _ => None,
            },
        })
        .collect()
}

fn clause_checks(
    clauses: &[ClauseSpec],
    kind_name: &str,
    contract_crate: &proc_macro2::TokenStream,
    function_path: &proc_macro2::TokenStream,
    inputs: &[proc_macro2::TokenStream],
) -> Vec<proc_macro2::TokenStream> {
    clause_checks_with_binding(
        clauses,
        kind_name,
        quote! {},
        contract_crate,
        function_path,
        inputs,
    )
}

fn clause_checks_with_binding(
    clauses: &[ClauseSpec],
    kind_name: &str,
    binding: proc_macro2::TokenStream,
    contract_crate: &proc_macro2::TokenStream,
    function_path: &proc_macro2::TokenStream,
    inputs: &[proc_macro2::TokenStream],
) -> Vec<proc_macro2::TokenStream> {
    let kind_ident = format_ident!("{kind_name}");

    clauses
        .iter()
        .map(|spec| {
            let expression = &spec.expr;
            let condition_text = condition_literal(expression);
            let message_tokens = option_literal(spec.message.as_ref());
            quote! {
                #binding
                if !(#expression) {
                    #contract_crate::handle_violation(
                        #contract_crate::violation(
                            #contract_crate::ContractKind::#kind_ident,
                            #function_path,
                            #condition_text,
                            #message_tokens,
                            #contract_crate::ContractLocation::new(file!(), line!(), column!()),
                            vec![#(#inputs),*]
                        )
                    );
                }
            }
        })
        .collect()
}

fn result_post_checks(
    clauses: &[ClauseSpec],
    contract_crate: &proc_macro2::TokenStream,
    function_path: &proc_macro2::TokenStream,
    inputs: &[proc_macro2::TokenStream],
) -> Vec<proc_macro2::TokenStream> {
    clauses
        .iter()
        .map(|spec| {
            let expression = &spec.expr;
            let condition_text = condition_literal(expression);
            let message_tokens = option_literal(spec.message.as_ref());
            quote! {
                if let Ok(ret) = &__contract_result {
                    if !(#expression) {
                        #contract_crate::handle_violation(
                            #contract_crate::violation(
                                #contract_crate::ContractKind::Postcondition,
                                #function_path,
                                #condition_text,
                                #message_tokens,
                                #contract_crate::ContractLocation::new(file!(), line!(), column!()),
                                vec![#(#inputs),*]
                            )
                        );
                    }
                }
            }
        })
        .collect()
}

fn result_error_checks(
    clauses: &[ClauseSpec],
    contract_crate: &proc_macro2::TokenStream,
    function_path: &proc_macro2::TokenStream,
    inputs: &[proc_macro2::TokenStream],
) -> proc_macro2::TokenStream {
    if clauses.is_empty() {
        return quote! {};
    }

    let message_literals = clauses
        .iter()
        .filter_map(|spec| spec.message.as_ref())
        .map(LitStr::value)
        .collect::<Vec<_>>();
    let expression_checks = clauses.iter().map(|spec| {
        let expression = &spec.expr;
        quote! {
            if #expression {
                __contract_error_matched = true;
            }
        }
    });

    let joined_conditions = LitStr::new(
        &normalize_condition_text(
            clauses
                .iter()
                .map(|spec| {
                    let expression = &spec.expr;
                    quote!(#expression).to_string()
                })
                .collect::<Vec<_>>()
                .join(" || "),
        ),
        Span::call_site(),
    );
    let joined_messages = if message_literals.is_empty() {
        None
    } else {
        Some(LitStr::new(
            &message_literals.join(" / "),
            Span::call_site(),
        ))
    };
    let message_tokens = option_literal(joined_messages.as_ref());

    quote! {
        if let Err(err) = &__contract_result {
            let mut __contract_error_matched = false;
            #(#expression_checks)*

            if !__contract_error_matched {
                #contract_crate::handle_violation(
                    #contract_crate::violation(
                        #contract_crate::ContractKind::ErrorContract,
                        #function_path,
                        #joined_conditions,
                        #message_tokens,
                        #contract_crate::ContractLocation::new(file!(), line!(), column!()),
                        vec![#(#inputs),*]
                    )
                );
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn metadata_entries(
    preconditions: &[ClauseSpec],
    postconditions: &[ClauseSpec],
    error_contracts: &[ClauseSpec],
    invariants: &[ClauseSpec],
    pure_marker: bool,
    purity_message: Option<&LitStr>,
    panic_free_marker: bool,
    panic_contract_message: Option<&LitStr>,
    contract_crate: &proc_macro2::TokenStream,
) -> Vec<proc_macro2::TokenStream> {
    let mut entries = Vec::new();

    entries.extend(metadata_clause_tokens(
        preconditions,
        "Precondition",
        contract_crate,
    ));
    entries.extend(metadata_clause_tokens(
        postconditions,
        "Postcondition",
        contract_crate,
    ));
    entries.extend(metadata_clause_tokens(
        invariants,
        "Invariant",
        contract_crate,
    ));
    entries.extend(metadata_clause_tokens(
        error_contracts,
        "ErrorContract",
        contract_crate,
    ));

    if pure_marker {
        let message = option_literal(purity_message);
        entries.push(quote! {
            #contract_crate::ContractClause::new(
                #contract_crate::ContractKind::Purity,
                "pure",
                #message
            )
        });
    }

    if panic_free_marker {
        let message = option_literal(panic_contract_message);
        entries.push(quote! {
            #contract_crate::ContractClause::new(
                #contract_crate::ContractKind::PanicContract,
                "panic_free",
                #message
            )
        });
    }

    if pure_marker && !panic_free_marker {
        entries.push(quote! {
            #contract_crate::ContractClause::new(
                #contract_crate::ContractKind::PanicContract,
                "panic_free",
                None
            )
        });
    }

    entries
}

fn metadata_clause_tokens(
    clauses: &[ClauseSpec],
    kind_name: &str,
    contract_crate: &proc_macro2::TokenStream,
) -> Vec<proc_macro2::TokenStream> {
    let kind_ident = format_ident!("{kind_name}");

    clauses
        .iter()
        .map(|spec| {
            let condition = condition_literal(&spec.expr);
            let message = option_literal(spec.message.as_ref());
            quote! {
                #contract_crate::ContractClause::new(
                    #contract_crate::ContractKind::#kind_ident,
                    #condition,
                    #message
                )
            }
        })
        .collect()
}

fn condition_literal(expression: &Expr) -> LitStr {
    let raw = quote!(#expression).to_string();
    LitStr::new(&normalize_condition_text(raw), expression.span())
}

fn normalize_condition_text(raw: String) -> String {
    raw.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .replace("! (", "!(")
        .replace(" :: ", "::")
        .replace(" . ", ".")
}

fn option_literal(value: Option<&LitStr>) -> proc_macro2::TokenStream {
    match value {
        Some(value) => quote!(Some(#value)),
        None => quote!(None),
    }
}
